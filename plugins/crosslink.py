import re

import crosslink
from crosslink.services import (
    GitHubService,
    GitLabService,
    GravatarService,
    KeybaseService,
    LibravatarService,
    OpenHubService,
)
from crosslink.identifiers import (
    Email,
    Identity,
    VerifiedAccount,
)

from errbot import BotPlugin, cmdfilter, re_botcmd

_cache = {}


class CrossLinkPlugin(BotPlugin):

    def __init__(self, bot, name=None):
        self._services = None
        super(CrossLinkPlugin, self).__init__(bot, name)

    def get_configuration_template(self):
        config = {
           'CROSSLINK_GITHUB_TOKEN': '',
           'CROSSLINK_GITLAB_TOKEN': '',
           'CROSSLINK_OPENHUB_TOKEN': '',
        }

        for key in config:
            if hasattr(self.bot_config, key):
                config[key] = getattr(self.bot_config, key)

        return config

    def _get_config(self, key):
        if self.config and key in self.config:
            return self.config[key]
        return getattr(self.bot_config, key, None)

    @property
    def services(self):
        if not self._services:
            services = {
                'gravatar': GravatarService(),
                'libravatar': LibravatarService(),
                'keybase': KeybaseService(),
            }
            token = self._get_config('CROSSLINK_GITHUB_TOKEN')
            if token and ':' in token:
                token = tuple(token.split(':', 1))
                services['github'] = GitHubService(token=token)
            token = self._get_config('CROSSLINK_GITLAB_TOKEN')
            if token:
                services['gitlab'] = GitLabService(token=token)
            token = self._get_config('CROSSLINK_OPENHUB_TOKEN')
            if token:
                services['openhub'] = OpenHubService(token=token)

            self._services = services

        return self._services

    def _get_email_nick(self, email):
        """Tries to obtain a nickname for an email address.

        Does not perform caching."""
        nick = None
        self.log.debug('looking up nick for %s' % email)
        try:
            start = Email(email)
        except Exception as e:
            self.log.exception('crosslink failed: %s' % e)

        results = crosslink.resolve(start, self.services.values())

        for item in results:
            for key in ['github', 'gitlab', 'openhub']:
                if key in self.services:
                    service = self.services[key]
                    if isinstance(item, service._identity_cls):
                        self.log.debug(
                            'found %s username %s for %s'
                            % (key, item.preferred_username, email))
                        nick = item.preferred_username
                        break

        return nick

    @cmdfilter
    def add_nick(self, msg, cmd, args, dry_run):
        def get_user_nick(person_self):
            if hasattr(self, '_nick'):
                return person_self._nick
            else:
                self.log.warning('_nick was not set')

        if not msg.frm.nick:
            email = msg.frm.emails[0]

            if not _cache.get(email):
                _cache[email] = self._get_email_nick(email)

            msg.frm._nick = _cache[email]
            msg.frm.__class__.nick = property(get_user_nick)

        return msg, cmd, args

    @re_botcmd(pattern=r'^crosslink(?:\s+([\w@.\-\+]+))',
               re_cmd_name_help='crosslink',
               flags=re.IGNORECASE)
    def crosslink_cmd(self, msg, match):
        """Unassign from an issue."""
        if len(match.groups()):
            email = match.group(1)
        else:
            email = msg.frm.emails[0]

        try:
            start = Email(email)
        except Exception as e:
            self.log.exception('crosslink failed: %s' % e)
            return 'Exception %r' % e

        results = crosslink.resolve(start, self.services.values())

        identities = []
        for item in results:
            if isinstance(item, Identity):
                identities.append(item)

        if not identities:
            return 'no identities found for `%s`!' % email

        output = ['Identities for `%s`:' % email]
        for identity in identities:
            output.append(str(identity))
            arranged = []
            for item in identity.get_fragments():
                if isinstance(item, VerifiedAccount):
                    arranged.insert(0, item)
                else:
                    arranged.append(item)

            for item in arranged:
                if isinstance(item, VerifiedAccount):
                    if item.verifier != identity.service:
                        output.append(' + %s' % str(item))
                    else:
                        output.append(' + %s' % str(item.account))
                else:
                    output.append('   ' + str(item))

        return '\n'.join(output)
