"""Portrait layout profiles for explicit editorial layers (pixels, 1080 × 1920).

Templates choose composition, never new facts or arbitrary effects. Specialized
actions remain explicit events in a validated timeline, as in the motion studies.
"""
from .models import Bounds
from agent.news_models import NewsError

def profile(name,count):
    ordinary=Bounds(x=105,y=380,w=870,h=240)
    lower=Bounds(x=105,y=1290,w=870,h=350)
    single=[Bounds(x=320,y=690,w=440,h=440)]
    compare=([Bounds(x=110+j*455,y=710,w=380,h=380) for j in range(count)] if count<=2
        else [Bounds(x=90+j*310,y=740,w=280,h=340) for j in range(count)])
    profiles={
        'single_subject':(ordinary,lower,single if count<=1 else compare),
        'comparison':(ordinary,lower,compare),
        'person_context':(ordinary,lower,[Bounds(x=335,y=730,w=410,h=430),Bounds(x=190,y=650,w=700,h=480)]),
        'object_location':(ordinary,lower,[Bounds(x=360,y=850,w=360,h=290),Bounds(x=170,y=650,w=740,h=480)]),
        'document_photo':(ordinary,Bounds(x=105,y=760,w=870,h=350),[Bounds(x=405,y=1130,w=270,h=270)]),
        'date_year':(ordinary,Bounds(x=105,y=1310,w=870,h=330),[Bounds(x=335,y=890,w=410,h=400)]),
        'location_transfer':(ordinary,lower,[Bounds(x=150,y=770,w=340,h=370),Bounds(x=590,y=770,w=340,h=370)]),
        'process':(ordinary,Bounds(x=370 if count else 105,y=790,w=610 if count else 870,h=350),[Bounds(x=100,y=810,w=220,h=240)]),
        'connector':(Bounds(x=105,y=710,w=870,h=240),Bounds(x=105,y=1110,w=870,h=350),[]),
        'conclusion':(ordinary,Bounds(x=105,y=1190,w=870,h=350),[Bounds(x=400,y=735,w=280,h=280)]),
    }
    if name not in profiles:raise NewsError('Unsupported editorial template: '+name)
    top,bottom,boxes=profiles[name]
    if count>1 and name in ('process','document_photo','conclusion'):
        # These profiles place text beside/above ONE image. Their multi-image
        # variants need a separate text band rather than text over a photo row.
        bottom=lower;boxes=compare
    if count>len(boxes):
        # Multi-entity variants use the explicit comparison arrangement, retaining
        # semantic text placement. No overlapping fourth-slot improvisation.
        if count>3:raise NewsError('Split a visual beat with more than three entities.')
        boxes=compare
    return top,bottom,boxes[:count]
