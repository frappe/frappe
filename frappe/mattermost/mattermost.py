import json
import logging
import time
import requests
import websocket

logger = logging.getLogger(__name__)


class MattermostAPI(object):
    def __init__(self, url):
        self.url = url
        self.token = ""

    def _get_headers(self):
        return {"Authorization": "Bearer " + self.token}

    def get(self, request):
        return json.loads(
            requests.get(self.url + request, headers=self._get_headers()).text)

    def post(self, request, data=None):
        return json.loads(requests.post(
            self.url + request,
            headers=self._get_headers(),
            data=json.dumps(data)
        ).text)

    def login(self, name, email, password):
        props = {'name': name, 'email': email, 'password': password}
        p = requests.post(self.url + '/users/login', data=json.dumps(props))
        self.token = p.headers["Token"]
        return json.loads(p.text)

    def create_post(self, user_id, channel_id, message, files=None, pid=""):
        create_at = int(time.time() * 1000)
        return self.post('/channels/%s/create' % channel_id, {
            'user_id': user_id,
            'channel_id': channel_id,
            'message': message,
            'create_at': create_at,
            'filenames': files or [],
            'pending_post_id': user_id + ':' + str(create_at),
            'state': "loading",
            'parent_id': pid,
            'root_id': pid,
        })

    def channel(self, channel_id):
        return self.get('/channels/%s/' % channel_id)

    def get_channel_posts(self, channel_id, since):
        return self.get('/channels/%s/posts/%s' % (channel_id, since))

    def get_channels(self):
        return self.get('/channels/').get('channels')

    def get_profiles(self):
        return self.get('/users/profiles')

    def me(self):
        return self.get('/users/me')

    def user(self, user_id):
        return self.get('/users/%s' % user_id)

    def hooks_list(self):
        return self.get('/hooks/incoming/list')

    def hooks_create(self, **kwargs):
        return self.post('/hooks/incoming/create', kwargs)

    @staticmethod
    def in_webhook(url, channel, text, username=None, as_user=None,
                   parse=None, link_names=None, attachments=None,
                   unfurl_links=None, unfurl_media=None, icon_url=None,
                   icon_emoji=None):
        return requests.post(
            url, data={
                'payload': json.dumps({
                    'channel': channel,
                    'text': text,
                    'username': username,
                    'as_user': as_user,
                    'parse': parse,
                    'link_names': link_names,
                    'attachments': attachments,
                    'unfurl_links': unfurl_links,
                    'unfurl_media': unfurl_media,
                    'icon_url': icon_url,
                    'icon_emoji': icon_emoji})
            })


class MattermostClient(object):
    def __init__(self, url, team, email, password):
        self.users = {}
        self.channels = {}
        self.mentions = {}
        self.api = MattermostAPI(url)
        self.user = None
        self.info = None
        self.websocket = None
        self.email = None
        self.team = team
        self.email = email
        self.password = password

        self.login(team, email, password)

    def login(self, team, email, password):
        self.email = email
        self.user = self.api.login(team, email, password)
        self.info = self.api.me()
        return self.user

    def channel_msg(self, channel, message, pid=""):
        c_id = self.channels.get(channel, {}).get("id") or channel
        return self.api.create_post(self.user["id"], c_id, message, pid=pid)

    def get_users(self):
        return self.api.get_profiles()

    def connect_websocket(self):
        host = self.api.url.replace('http', 'ws').replace('https', 'wss')
        url = host + '/websocket?session_token_index=0&1'
        self.websocket = websocket.create_connection(
            url, header=[
                "Cookie: MMTOKEN=%s" % self.api.token,
            ]
            # ,timeout=1
        )
        return self.websocket.getstatus() == 101

    def messages(self, ignore_own_msg=False, filter_action=None):
        if not self.connect_websocket():
            return
        while True:
            data = self.websocket.recv()
            if data:
                try:
                    post = json.loads(data)
                    if filter_action and post.get('action') != filter_action:
                        continue
                    if ignore_own_msg is True and post.get("user_id"):
                        if self.user["id"] == post.get("user_id"):
                            continue
                    if post.get('props', {}).get('post'):
                        post['props']['post'] = json.loads(
                            post['props']['post'])
                    yield post
                except ValueError:
                    pass

    def ping(self):
        self.websocket.ping()

