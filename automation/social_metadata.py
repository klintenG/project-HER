"""Story-grounded platform copy; no invented trend claims or extra model call."""
import re


class SocialMetadataGenerator:
    def generate(self,story):
        tags=[]
        for value in [story['category'],*story.get('primary_characters',[])[:2],'ProjectHER']:
            tag='#'+''.join(re.findall(r'[A-Za-z0-9]+',value.title()))
            if tag not in tags and len(tag)>1:tags.append(tag)
        framing=('An original fictional story.' if story['story_origin']=='ORIGINAL_FICTION'
                 else 'A retelling from '+story['mythology_tradition']+'.')
        references='\n'.join(story.get('supporting_references',[]))
        summary=story['story_summary']
        return {'youtube_title':story['title'][:100],
            'youtube_description':(summary+'\n\n'+framing+' AI-assisted visuals and narration.\n'+references+'\n\n'+' '.join(tags+['#Shorts']))[:5000],
            'instagram_caption':(story['script']['hook_text']+'\n\n'+summary+'\n\n'+framing+' AI-assisted visuals and narration.\n\n'+' '.join(tags))[:2200],
            'hashtags':tags,'keywords':story.get('primary_characters',[])+[story['category']],
            'youtube_cover_status':'YouTube determines the Shorts thumbnail; Buffer cannot select it.'}
