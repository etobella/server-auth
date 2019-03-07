# (c) 2015 ACSONE SA/NV, Dhinesh D

# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html).

from time import time
import odoo
from odoo.http import SessionExpiredException, request
from odoo import http
from odoo.tools.func import lazy_property
from odoo import api, models


def patch_session_store(method):
    def patched_session_store():
        store = method

        class OpenERPSessionUpdate(store.session_class):
            def check_security(self):
                super().check_security()
                env = odoo.api.Environment(
                    request.cr, self.uid, self.context)
                delay = env['res.users']._auth_timeout_deadline_calculate()
                if delay and self.update_time and self.update_time < delay:
                    self.logout(keep_db=True)
                    raise SessionExpiredException("Session expired")
                ignored_urls = env[
                    'res.users'
                ]._auth_timeout_get_ignored_urls()
                if http.request.httprequest.path not in ignored_urls:
                    self.update_time = time()

            def _default_values(self):
                super()._default_values()
                self.setdefault("update_time", False)

            def authenticate(self, db, login=None, password=None, uid=None):
                res = super().authenticate(
                    db, login=login, password=password, uid=uid)
                if not self.update_time:
                    self.update_time = time()
                return res

        store.session_class = OpenERPSessionUpdate
        return store

    patched_session_store.__decorated_session_timeout__ = True
    return patched_session_store()


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_cr
    def _register_hook(self):
        # if not hasattr(
        #     http.root.session_store, '__decorated_session_timeout__'
        # ):
        http.root.session_store = patch_session_store(http.root.session_store)
        return super()._register_hook()

    @api.model_cr_context
    def _auth_timeout_get_ignored_urls(self):
        """Pluggable method for calculating ignored urls
        Defaults to stored config param
        """
        params = self.env['ir.config_parameter']
        return params._auth_timeout_get_parameter_ignored_urls()

    @api.model_cr_context
    def _auth_timeout_deadline_calculate(self):
        """Pluggable method for calculating timeout deadline
        Defaults to current time minus delay using delay stored as config
        param.
        """
        params = self.env['ir.config_parameter']
        delay = params._auth_timeout_get_parameter_delay()
        if delay <= 0:
            return False
        return time() - delay
