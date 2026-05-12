import torch
import torch.nn as nn
from typing import List
from torchtune.modules import RotaryPositionalEmbeddings
from vector_quantize_pytorch import ResidualFSQ
from .bs_roformer5 import TransformerBlock

class ISTFT(nn.Module):

    def __init__(self, n_fft: int, hop_length: int, win_length: int, padding: str='same'):
        super().__init__()
        if padding not in ['center', 'same']:
            raise ValueError("Padding must be 'center' or 'same'.")
        self.padding = padding
        self.n_fft = n_fft
        self.hop_length = hop_length
        self.win_length = win_length
        window = torch.hann_window(win_length)
        self.register_buffer('window', window)

    def forward(self, spec: torch.Tensor) -> torch.Tensor:
        if self.padding == 'center':
            return torch.istft(spec, self.n_fft, self.hop_length, self.win_length, self.window, center=True)
        elif self.padding == 'same':
            pad = (self.win_length - self.hop_length) // 2
        else:
            raise ValueError("Padding must be 'center' or 'same'.")
        assert spec.dim() == 3, 'Expected a 3D tensor as input'
        B, N, T = spec.shape
        ifft = torch.fft.irfft(spec, self.n_fft, dim=1, norm='backward')
        ifft = ifft * self.window[None, :, None]
        output_size = (T - 1) * self.hop_length + self.win_length
        y = torch.nn.functional.fold(ifft, output_size=(1, output_size), kernel_size=(1, self.win_length), stride=(1, self.hop_length))[:, 0, 0, pad:-pad]
        window_sq = self.window.square().expand(1, T, -1).transpose(1, 2)
        window_envelope = torch.nn.functional.fold(window_sq, output_size=(1, output_size), kernel_size=(1, self.win_length), stride=(1, self.hop_length)).squeeze()[pad:-pad]
        assert (window_envelope > 1e-11).all()
        y = y / window_envelope
        return y

class FourierHead(nn.Module):

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        raise NotImplementedError('Subclasses must implement the forward method.')

class ISTFTHead(FourierHead):

    def __init__(self, dim: int, n_fft: int, hop_length: int, padding: str='same'):
        super().__init__()
        out_dim = n_fft + 2
        self.out = torch.nn.Linear(dim, out_dim)
        self.istft = ISTFT(n_fft=n_fft, hop_length=hop_length, win_length=n_fft, padding=padding)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x_pred = self.out(x)
        x_pred = x_pred.transpose(1, 2)
        mag, p = x_pred.chunk(2, dim=1)
        mag = torch.exp(mag)
        mag = torch.clip(mag, max=100.0)
        x = torch.cos(p)
        y = torch.sin(p)
        S = mag * (x + 1j * y)
        audio = self.istft(S)
        return (audio.unsqueeze(1), x_pred)

def nonlinearity(x):
    return x * torch.sigmoid(x)

def Normalize(in_channels, num_groups=32):
    return torch.nn.GroupNorm(num_groups=num_groups, num_channels=in_channels, eps=1e-06, affine=True)

class ResnetBlock(nn.Module):

    def __init__(self, *, in_channels, out_channels=None, conv_shortcut=False, dropout, temb_channels=512):
        super().__init__()
        self.in_channels = in_channels
        out_channels = in_channels if out_channels is None else out_channels
        self.out_channels = out_channels
        self.use_conv_shortcut = conv_shortcut
        self.norm1 = Normalize(in_channels)
        self.conv1 = torch.nn.Conv1d(in_channels, out_channels, kernel_size=3, stride=1, padding=1)
        if temb_channels > 0:
            self.temb_proj = torch.nn.Linear(temb_channels, out_channels)
        self.norm2 = Normalize(out_channels)
        self.dropout = torch.nn.Dropout(dropout)
        self.conv2 = torch.nn.Conv1d(out_channels, out_channels, kernel_size=3, stride=1, padding=1)
        if self.in_channels != self.out_channels:
            if self.use_conv_shortcut:
                self.conv_shortcut = torch.nn.Conv1d(in_channels, out_channels, kernel_size=3, stride=1, padding=1)
            else:
                self.nin_shortcut = torch.nn.Conv1d(in_channels, out_channels, kernel_size=1, stride=1, padding=0)

    def forward(self, x, temb=None):
        h = x
        h = self.norm1(h)
        h = nonlinearity(h)
        h = self.conv1(h)
        if temb is not None:
            h = h + self.temb_proj(nonlinearity(temb))[:, :, None, None]
        h = self.norm2(h)
        h = nonlinearity(h)
        h = self.dropout(h)
        h = self.conv2(h)
        if self.in_channels != self.out_channels:
            if self.use_conv_shortcut:
                x = self.conv_shortcut(x)
            else:
                x = self.nin_shortcut(x)
        return x + h

class Backbone(nn.Module):

    def forward(self, x: torch.Tensor, **kwargs) -> torch.Tensor:
        raise NotImplementedError('Subclasses must implement the forward method.')

class VocosBackbone(Backbone):

    def __init__(self, hidden_dim=1024, depth=12, heads=16, pos_meb_dim=64):
        super().__init__()
        self.embed = nn.Conv1d(hidden_dim, hidden_dim, kernel_size=7, padding=3)
        self.temb_ch = 0
        block_in = hidden_dim
        dropout = 0.1
        prior_net: List[nn.Module] = [ResnetBlock(in_channels=block_in, out_channels=block_in, temb_channels=self.temb_ch, dropout=dropout), ResnetBlock(in_channels=block_in, out_channels=block_in, temb_channels=self.temb_ch, dropout=dropout)]
        self.prior_net = nn.Sequential(*prior_net)
        depth = depth
        time_rotary_embed = RotaryPositionalEmbeddings(dim=pos_meb_dim)
        transformer_blocks = [TransformerBlock(dim=hidden_dim, n_heads=heads, rotary_embed=time_rotary_embed) for _ in range(depth)]
        self.transformers = nn.Sequential(*transformer_blocks)
        self.final_layer_norm = nn.LayerNorm(hidden_dim, eps=1e-06)
        post_net: List[nn.Module] = [ResnetBlock(in_channels=block_in, out_channels=block_in, temb_channels=self.temb_ch, dropout=dropout), ResnetBlock(in_channels=block_in, out_channels=block_in, temb_channels=self.temb_ch, dropout=dropout)]
        self.post_net = nn.Sequential(*post_net)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x.transpose(1, 2)
        x = self.embed(x)
        x = self.prior_net(x)
        x = x.transpose(1, 2)
        x = self.transformers(x)
        x = x.transpose(1, 2)
        x = self.post_net(x)
        x = x.transpose(1, 2)
        x = self.final_layer_norm(x)
        return x

def init_weights(m):
    if isinstance(m, nn.Conv1d):
        nn.init.trunc_normal_(m.weight, std=0.02)
        nn.init.constant_(m.bias, 0)

class CodecDecoderVocos(nn.Module):

    def __init__(self, hidden_dim=1024, depth=12, heads=16, pos_meb_dim=64, hop_length=320, vq_num_quantizers=1, vq_dim=2048, vq_commit_weight=0.25, vq_weight_init=False, vq_full_commit_loss=False, codebook_size=16384, codebook_dim=16):
        super().__init__()
        self.hop_length = hop_length
        self.quantizer = ResidualFSQ(dim=vq_dim, levels=[4, 4, 4, 4, 4, 4, 4, 4], num_quantizers=1)
        self.backbone = VocosBackbone(hidden_dim=hidden_dim, depth=depth, heads=heads, pos_meb_dim=pos_meb_dim)
        self.head = ISTFTHead(dim=hidden_dim, n_fft=self.hop_length * 4, hop_length=self.hop_length, padding='same')
        self.reset_parameters()

    def forward(self, x, vq=True):
        if vq is True:
            x = x.permute(0, 2, 1)
            x, q = self.quantizer(x)
            x = x.permute(0, 2, 1)
            q = q.permute(0, 2, 1)
            return (x, q, None)
        x = self.backbone(x)
        x, _ = self.head(x)
        return (x, _)

    def vq2emb(self, vq):
        self.quantizer = self.quantizer.eval()
        x = self.quantizer.vq2emb(vq)
        return x

    def get_emb(self):
        self.quantizer = self.quantizer.eval()
        embs = self.quantizer.get_emb()
        return embs

    def inference_vq(self, vq):
        x = vq[None, :, :]
        x = self.model(x)
        return x

    def inference_0(self, x):
        x, q, loss, perp = self.quantizer(x)
        x = self.model(x)
        return (x, None)

    def inference(self, x):
        x = self.model(x)
        return (x, None)

    def remove_weight_norm(self):

        def _remove_weight_norm(m):
            try:
                torch.nn.utils.remove_weight_norm(m)
            except ValueError:
                return
        self.apply(_remove_weight_norm)

    def apply_weight_norm(self):

        def _apply_weight_norm(m):
            if isinstance(m, nn.Conv1d) or isinstance(m, nn.ConvTranspose1d):
                torch.nn.utils.weight_norm(m)
        self.apply(_apply_weight_norm)

    def reset_parameters(self):
        self.apply(init_weights)