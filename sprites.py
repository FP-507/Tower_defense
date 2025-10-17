import pygame, math
from config import RAND

def make_tower_sprite(kind):
    small_size = 28
    small = pygame.Surface((small_size, small_size), pygame.SRCALPHA)
    pals = {
        'basic': ((50,90,140),(200,220,240)),
        'slow': ((120,70,150),(200,180,240)),
        'splash': ((90,130,60),(240,230,140)),
        'rapid': ((20,140,150),(180,240,240)),
        'multi': ((160,100,40),(240,200,160)),
        'pierce': ((170,50,50),(255,200,200)),
        'ultimate': ((210,170,60),(255,230,120))
    }
    base, accent = pals.get(kind, ((100,100,100),(220,220,220)))
    small.fill((0,0,0,0))
    cx = small_size//2; cy = small_size//2
    for y in range(small_size):
        for x in range(small_size):
            d = math.hypot(x-cx, y-cy)
            if d <= 9.0:
                small.set_at((x,y), base)
            elif d <= 10.5:
                rim = tuple(max(0, c-30) for c in base)
                small.set_at((x,y), rim)
    hl = tuple(min(255, c+30) for c in base)
    for ox,oy in ((-2,-2),(-1,-2),(-2,-1)):
        px = cx+ox; py = cy+oy
        if 0<=px<small_size and 0<=py<small_size: small.set_at((px,py), hl)
    def put(px,py,col):
        if 0<=px<small_size and 0<=py<small_size: small.set_at((px,py), col)
    if kind == 'basic':
        for y in range(-4,5): put(cx, cy+y, accent)
        put(cx, cy-6, accent)
    elif kind == 'slow':
        for i in range(-4,5): put(cx+i, cy, accent); put(cx, cy+i, accent)
    elif kind == 'splash':
        put(cx,cy-6,accent); put(cx-2,cy-4,accent); put(cx+2,cy-4,accent); put(cx,cy-3,accent)
    elif kind == 'rapid':
        for ox in (-4,0,4):
            for y in range(-3,1): put(cx+ox, cy+y, accent)
    elif kind == 'multi':
        for ox in (-6,0,6): put(cx+ox, cy-2, accent); put(cx+ox, cy-1, accent)
    elif kind == 'pierce':
        for i in range(0,6): put(cx+i, cy, accent)
    elif kind == 'ultimate':
        for dy in (-6,-4,-2,0): put(cx, cy+dy, accent)
        put(cx-3, cy-2, accent); put(cx+3, cy-2, accent)
    put(cx, cy+6, (20,20,28))
    s = pygame.transform.scale(small, (56,56))
    return s

def make_enemy_sprite(kind):
    small_w = 22; small_h = 22
    small = pygame.Surface((small_w, small_h), pygame.SRCALPHA)
    small.fill((0,0,0,0))
    pal = {
        'scout': (200,240,120),
        'grunt': (200,60,60),
        'tank': (120,120,200),
        'sapper': (220,150,80)
    }
    col = pal.get(kind, (180,180,180))
    cx = small_w//2; cy = small_h//2
    for y in range(small_h):
        for x in range(small_w):
            d = math.hypot(x-cx, y-cy)
            if d <= 8.5:
                small.set_at((x,y), col)
            elif d <= 9.6:
                rim = tuple(max(0, c-40) for c in col)
                small.set_at((x,y), rim)
    def put(px,py,c):
        if 0<=px<small_w and 0<=py<small_h: small.set_at((px,py), c)
    if kind == 'scout':
        put(cx+4,cy-2,(255,255,220)); put(cx-2,cy,(140,200,80))
        for dx in (-1,1): put(cx+3, cy+2+dx, (220,220,220))
    elif kind == 'grunt':
        for x in range(cx-5, cx+6): put(x, cy, (24,24,24))
    elif kind == 'tank':
        for x in range(cx-6, cx+7): put(x, cy-2, (40,40,60))
        put(cx+6, cy-3, (100,120,200)); put(cx-6, cy-3, (100,120,200))
    elif kind == 'sapper':
        for x in range(cx-3, cx+4): put(x, cy, (40,30,30))
        put(cx+6, cy-5, (255,200,100))
    else:
        put(cx,cy,(220,220,220))
    s = pygame.transform.scale(small, (44,44))
    return s

# pre-generate sprites
SPRITES = {}
for k in ('basic','slow','splash','rapid','multi','pierce','ultimate'):
    SPRITES['tower_'+k] = make_tower_sprite(k)
for k in ('scout','grunt','tank','sapper'):
    SPRITES['enemy_'+k] = make_enemy_sprite(k)
