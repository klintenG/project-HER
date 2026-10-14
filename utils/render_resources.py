"""Server-controlled render limits; native workers stay within container RAM."""
import os


def remotion_concurrency(default=2):
    return max(1,min(default,int(os.getenv('HER_REMOTION_CONCURRENCY',str(default)))))
