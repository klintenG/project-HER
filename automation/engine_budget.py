"""Optional per-worker request ceiling; no effect on manual generation.

Reservations are conservative operator-configured estimates, not provider bills.
Every attempted image request (including fallbacks/retries) consumes its ceiling.
"""
from contextvars import ContextVar
from threading import Lock

active_budget=ContextVar('her_autopilot_engine_budget',default=None)


class EngineBudget:
    def __init__(self,limit,image_price,max_images,registry,sid):
        self.limit=limit;self.image_price=image_price;self.max_images=max_images
        self.registry=registry;self.sid=sid;self.spent=0;self.count=0;self.lock=Lock();self.entries=[]
    def charge_image(self,provider):
        with self.lock:
            if self.count>=self.max_images or self.spent+self.image_price>self.limit:
                raise ValueError('Autopilot image request/cost ceiling reached')
            self.count+=1;self.spent+=self.image_price
            self.entries.append({'component':'images','provider':provider,'reserved_usd':self.image_price})
            self.registry.store.set('engine-usage:'+self.sid,{'image_requests':self.count,'estimated_image_usd':self.spent,
                'actual_usd':None,'entries':self.entries})


def charge_image(provider):
    budget=active_budget.get()
    if budget is not None:budget.charge_image(provider)
