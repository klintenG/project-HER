"""Current Buffer GraphQL API. Mutations are never automatically retried."""
from __future__ import annotations
import os
import requests

POST_FIELDS = 'id channelId text dueAt status schedulingType externalLink error { message } assets { source }'


class BufferRejected(RuntimeError): pass


class BufferClient:
    def __init__(self, key=None, organization=None, session=None):
        self.key=key if key is not None else os.getenv('BUFFER_API_KEY','')
        self.organization=organization if organization is not None else os.getenv('BUFFER_ORGANIZATION_ID','')
        self.session=session or requests.Session()
    def query(self, query, variables=None):
        if not self.key:raise BufferRejected('BUFFER_API_KEY is not configured')
        response=self.session.post('https://api.buffer.com',headers={'Authorization':'Bearer '+self.key},
            json={'query':query,'variables':variables or {}},timeout=(10,45))
        # Even 5xx responses to a mutation can be ambiguous. Caller records UNKNOWN.
        if response.status_code in (400,401,403,429):
            raise BufferRejected('Buffer HTTP '+str(response.status_code))
        response.raise_for_status();body=response.json()
        if body.get('errors'):
            message='; '.join(e.get('message','GraphQL error') for e in body['errors'])
            if all(e.get('extensions',{}).get('code')=='GRAPHQL_VALIDATION_FAILED' for e in body['errors']):
                raise BufferRejected(message)
            raise RuntimeError('Ambiguous Buffer GraphQL error: '+message)
        return body['data']
    def discover(self):
        if not self.organization:
            organizations=self.query('query { account { organizations { id name } } }')['account']['organizations']
            if len(organizations)!=1:raise BufferRejected('Configure BUFFER_ORGANIZATION_ID; organization is ambiguous')
            self.organization=organizations[0]['id']
        channels=self.query('query($input: ChannelsInput!) { channels(input:$input) { id service displayName isDisconnected isLocked allowedActions type metadata { ... on InstagramMetadata { defaultToReminders } ... on YoutubeMetadata { defaultToReminders } } } }',
            {'input':{'organizationId':self.organization}})['channels']
        selected={}
        for platform in ('instagram','youtube'):
            configured=os.getenv('BUFFER_'+platform.upper()+'_CHANNEL_ID','')
            matches=[c for c in channels if c['service']==platform and (not configured or c['id']==configured)]
            if len(matches)!=1:raise BufferRejected('Configure one '+platform+' channel ID')
            channel=matches[0]
            if channel['isDisconnected'] or channel['isLocked']:raise BufferRejected(platform+' channel disconnected or locked')
            if 'scheduleUpdates' not in channel['allowedActions']:raise BufferRejected(platform+' scheduling permission unavailable')
            if channel.get('metadata',{}).get('defaultToReminders',True):
                raise BufferRejected(platform+' channel defaults to reminder publishing; configure automatic publishing first')
            selected[platform]=channel
        return selected
    def posts(self, channel):
        if not self.organization:raise BufferRejected('Resolve organization before querying posts')
        after=None;rows=[]
        # Bounded pagination fails closed rather than considering an incomplete queue empty.
        for _ in range(100):
            result=self.query('query($input: PostsInput!, $after: String) { posts(input:$input, first:100, after:$after) { edges { node { '+POST_FIELDS+' } } pageInfo { hasNextPage endCursor } } }',
                {'input':{'organizationId':self.organization,'filter':{'channelIds':[channel]}},'after':after})['posts']
            rows.extend(e['node'] for e in result['edges'])
            if not result['pageInfo']['hasNextPage']:return rows
            after=result['pageInfo']['endCursor']
        raise BufferRejected('Remote history pagination exceeded reconciliation ceiling')
    def get(self, post_id):
        return self.query('query($input: PostInput!) { post(input:$input) { '+POST_FIELDS+' } }',{'input':{'id':post_id}})['post']
    def create(self, payload):
        data=self.query('mutation($input: CreatePostInput!) { createPost(input:$input) { ... on PostActionSuccess { post { '+POST_FIELDS+' } } ... on MutationError { message } } }',{'input':payload})['createPost']
        if not data.get('post'):raise BufferRejected(data.get('message','Buffer rejected post'))
        return data['post']

    def edit(self, payload):
        result=self.query('mutation($input: EditPostInput!) { editPost(input:$input) { ... on PostActionSuccess { post { '+POST_FIELDS+' } } ... on MutationError { message } } }',{'input':payload})['editPost']
        if not result.get('post'):raise BufferRejected(result.get('message','Buffer rejected edit'))
        return result['post']


def build_post(platform, channel, media_url, due_at, metadata, offset):
    if platform not in ('instagram','youtube'):raise ValueError('Unsupported platform')
    asset={'url':media_url}
    if platform=='instagram':
        asset['metadata']={'thumbnailOffset':int(offset)}
        specific={'instagram':{'type':'reel','shouldShareToFeed':True,'isAiGenerated':True}}
        text=metadata['instagram_caption']
    else:
        specific={'youtube':{'title':metadata['youtube_title'],'categoryId':os.getenv('BUFFER_YOUTUBE_CATEGORY_ID','24'),
            'privacy':os.getenv('BUFFER_YOUTUBE_PRIVACY','public'),'madeForKids':False,'isAiGenerated':True}}
        text=metadata['youtube_description']
    return {'channelId':channel,'text':text,'schedulingType':'automatic','mode':'customScheduled',
            'dueAt':due_at,'assets':[{'video':asset}],'metadata':specific,'aiAssisted':True,
            'needsApproval':False,'saveToDraft':False}
