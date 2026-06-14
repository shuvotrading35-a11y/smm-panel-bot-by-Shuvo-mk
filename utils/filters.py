from telegram.ext import filters
from config import ADMIN_IDS


class AdminFilter(filters.BaseFilter):
    def filter(self, message):
        return message.from_user and message.from_user.id in ADMIN_IDS


class NotAdminFilter(filters.BaseFilter):
    def filter(self, message):
        return message.from_user and message.from_user.id not in ADMIN_IDS


admin_filter    = AdminFilter()
not_admin_filter = NotAdminFilter()
