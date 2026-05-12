import json
import os
from datetime import datetime, date
from typing import Dict, Any
import logging
logger = logging.getLogger(__name__)

class StatsManager:

    def __init__(self, stats_file: str='queue_data/stats.json'):
        self.stats_file = stats_file
        self._init_stats_file()

    def _init_stats_file(self):
        try:
            os.makedirs(os.path.dirname(self.stats_file), exist_ok=True)
            if not os.path.exists(self.stats_file):
                default_stats = {'total_processed': 0, 'total_failed': 0, 'daily_stats': {}, 'last_updated': None}
                self._save_stats(default_stats)
                logger.info('Đã khởi tạo file stats mới')
        except Exception as e:
            logger.error(f'Lỗi khởi tạo stats file: {e}')

    def _load_stats(self) -> Dict[str, Any]:
        try:
            if os.path.exists(self.stats_file):
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    content = f.read().strip()
                    if content:
                        return json.loads(content)
        except Exception as e:
            logger.error(f'Lỗi load stats: {e}')
        return {'total_processed': 0, 'total_failed': 0, 'daily_stats': {}, 'last_updated': None}

    def _save_stats(self, stats: Dict[str, Any]):
        try:
            stats['last_updated'] = datetime.now().isoformat()
            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f'Lỗi lưu stats: {e}')

    def increment_processed(self, count: int=1):
        try:
            stats = self._load_stats()
            stats['total_processed'] += count
            today = date.today().isoformat()
            if today not in stats['daily_stats']:
                stats['daily_stats'][today] = {'processed': 0, 'failed': 0}
            stats['daily_stats'][today]['processed'] += count
            self._save_stats(stats)
            logger.info(f'Đã cập nhật stats: +{count} processed')
        except Exception as e:
            logger.error(f'Lỗi cập nhật processed stats: {e}')

    def increment_failed(self, count: int=1):
        try:
            stats = self._load_stats()
            stats['total_failed'] += count
            today = date.today().isoformat()
            if today not in stats['daily_stats']:
                stats['daily_stats'][today] = {'processed': 0, 'failed': 0}
            stats['daily_stats'][today]['failed'] += count
            self._save_stats(stats)
            logger.info(f'Đã cập nhật stats: +{count} failed')
        except Exception as e:
            logger.error(f'Lỗi cập nhật failed stats: {e}')

    def get_today_stats(self) -> Dict[str, int]:
        try:
            stats = self._load_stats()
            today = date.today().isoformat()
            if today in stats['daily_stats']:
                return stats['daily_stats'][today]
            else:
                return {'processed': 0, 'failed': 0}
        except Exception as e:
            logger.error(f'Lỗi lấy today stats: {e}')
            return {'processed': 0, 'failed': 0}

    def get_total_stats(self) -> Dict[str, int]:
        try:
            stats = self._load_stats()
            return {'total_processed': stats.get('total_processed', 0), 'total_failed': stats.get('total_failed', 0)}
        except Exception as e:
            logger.error(f'Lỗi lấy total stats: {e}')
            return {'total_processed': 0, 'total_failed': 0}

    def get_all_stats(self) -> Dict[str, Any]:
        try:
            stats = self._load_stats()
            today_stats = self.get_today_stats()
            return {'total_processed': stats.get('total_processed', 0), 'total_failed': stats.get('total_failed', 0), 'today_processed': today_stats.get('processed', 0), 'today_failed': today_stats.get('failed', 0), 'daily_stats': stats.get('daily_stats', {}), 'last_updated': stats.get('last_updated')}
        except Exception as e:
            logger.error(f'Lỗi lấy all stats: {e}')
            return {'total_processed': 0, 'total_failed': 0, 'today_processed': 0, 'today_failed': 0, 'daily_stats': {}, 'last_updated': None}

    def cleanup_old_daily_stats(self, days_to_keep: int=30):
        try:
            stats = self._load_stats()
            daily_stats = stats.get('daily_stats', {})
            dates = sorted(daily_stats.keys(), reverse=True)
            if len(dates) > days_to_keep:
                dates_to_remove = dates[days_to_keep:]
                for date_to_remove in dates_to_remove:
                    del daily_stats[date_to_remove]
                stats['daily_stats'] = daily_stats
                self._save_stats(stats)
                logger.info(f'Đã dọn dẹp {len(dates_to_remove)} ngày thống kê cũ')
        except Exception as e:
            logger.error(f'Lỗi dọn dẹp old stats: {e}')
stats_manager = StatsManager()