"""Resolve names from evidence and acquire secondary portrait references."""
from pathlib import Path
from urllib.parse import urljoin
import hashlib
import re
from bs4 import BeautifulSoup
import config
from agent.news_models import NewsError
from agent.news_references import ReferencePhoto, ReferencePhotos, _safe_image
from agent.news_research import SerperSearch, extract, fetch, source_passages


class People:
    def resolve(self,entity,evidence,llm,diagnostics=None):
        if entity.identity!='real':
            return {'kind':entity.identity,'sources':[],'references':[]}
        refs=[];errors=[]
        try:refs=ReferencePhotos().find(entity,llm)
        except Exception as exc:errors.append('Commons lookup: '+type(exc).__name__)
        sources=[s for s in evidence.sources if s.id!='input' and s.url] if evidence else []
        if refs and any(r.death_date for r in refs):
            return {'kind':'historical','sources':[r.entity_url for r in refs],'deathDate':next(r.death_date for r in refs if r.death_date),'references':refs,'errors':errors}
        # A licensed linked portrait already establishes a usable source. The
        # evidence still lets the classifier distinguish historical depictions.
        if not refs:
            for result in SerperSearch().search((entity.reference_query or entity.name)+' biography portrait')[:3]:
                try:
                    body,url=fetch(result['url']);source=extract(body,url,'person-source-'+str(len(sources)))
                    sources.append(source)
                    soup=BeautifulSoup(body,'html.parser')
                    image=soup.find('meta',attrs={'property':'og:image'}) or soup.find('meta',attrs={'name':'twitter:image'})
                    if image and image.get('content'):
                        data,_=fetch(urljoin(url,image['content']),types=('image/jpeg','image/png','image/webp'),limit=15_000_000)
                        _safe_image(data)
                        root=config.NEWS_REFERENCE_CACHE/'web-reference';root.mkdir(parents=True,exist_ok=True)
                        path=root/(hashlib.sha256(data).hexdigest()+'.image');path.write_bytes(data)
                        refs.append(ReferencePhoto(str(path.resolve()),url,'Reference only; original rights retained',source.title,url))
                except Exception as exc:errors.append('Web portrait lookup: '+type(exc).__name__)
        if not llm:
            if refs and all(r.entity_url.startswith('https://www.wikidata.org/wiki/Q') for r in refs):
                return {'kind':'real','sources':[r.entity_url for r in refs],'references':refs,'errors':errors}
            raise NewsError('An evidence-based identity check is required for '+entity.name+'.')
        passages=source_passages(sources)
        rows=[{'id':s.id,'url':s.url,'passages':passages[s.id]} for s in sources]
        feedback=[]
        attempts=[]
        if diagnostics is not None:diagnostics['identityAttempts']=attempts
        for _ in range(2):
            answer=llm('Resolve this named person against the supplied source bodies and identity-linked portrait records. Return exactly {kind: "real"|"historical"|"fictional"|"unknown", source_id: string or null, passage_id: string or null, reason: string}. Copy source_id and passage_id from the supplied records; do not write your own quote. Historical means a deceased historical person, not a fictional person; select an explicit death/execution passage. If death is not stated, choose real when the sources establish an actual person. A person who acted in films can still be a real politician. Distinguish namesakes using role/place/context. Do not infer identity or current office from memory. A linked Wikidata portrait can support real even if source_id and passage_id are null. Fictional requires explicit source support. Unknown means insufficient evidence.',
                {'entity':entity.model_dump(),'sources':rows,'linked_portraits':[r.entity_url for r in refs if r.entity_url.startswith('https://www.wikidata.org/wiki/Q')],'repair_feedback':feedback})
            attempts.append(answer)
            if isinstance(answer,dict) and answer.get('kind') in ('real','historical','fictional'):
                source=next((s for s in sources if s.id==answer.get('source_id')),None)
                passage=next((p for p in passages.get(answer.get('source_id'),[]) if p['id']==answer.get('passage_id')),None)
                quote=passage['text'] if passage else answer.get('excerpt')
                supported=source is not None and isinstance(quote,str) and bool(quote.strip()) and quote in source.text
                linked=answer['kind']=='real' and any(r.entity_url.startswith('https://www.wikidata.org/wiki/Q') for r in refs)
                historical=answer['kind']!='historical' or (supported and re.search(r'\b(died|death|executed|hanged|assassinated|killed|deceased)\b',quote,re.I))
                if (supported or linked) and historical:
                    # A web page must independently support the selected person;
                    # unrelated search hits cannot supply their reference face.
                    refs=[r for r in refs if r.entity_url.startswith('https://www.wikidata.org/wiki/Q') or (source and r.source_url==source.url)]
                    return {'kind':answer['kind'],'sources':[source.url or source.id] if supported else [r.entity_url for r in refs],
                        'excerpt':quote if supported else '', 'references':refs,'errors':errors}
            feedback=['Return real/historical/fictional using a supplied source_id and passage_id. Historical needs an explicit death passage; otherwise select real if actual existence is supported. Do not paraphrase passage IDs.']
        raise NewsError('Could not establish the identity of '+entity.name+' from retrieved sources. Provide an article or audited portrait reference to distinguish namesakes.')
