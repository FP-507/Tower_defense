# tower_defense_final_optimized.py
# Versión optimizada del Tower Defense final (mismas funcionalidades que la versión anterior).
# Guarda y ejecuta. Requiere pygame.

import pygame, sys, math, heapq, random
from collections import deque

# -----------------------
# CONFIG
# -----------------------
TILE_SIZE = 36
GRID_W = 18
GRID_H = 13
SCREEN_W = TILE_SIZE * GRID_W
SCREEN_H = TILE_SIZE * GRID_H + 140
FPS = 60

START_MONEY = 300
TOWER_COST = 70
ULTIMATE_COST = 400

PROJECTILE_SPEED = 12
ENEMY_REPATH_INTERVAL = 36

BASE_WAVE_COUNT = 2
WAVE_INCREMENT = 2
WAVE_BASE_INTERVAL = 28
WAVE_MIN_INTERVAL = 8

SHADOW_OFFSET = 6
PARTICLE_COUNT = 14
DAMAGE_POPUP_LIFE = 0.9

# colors
WHITE = (255,255,255)
BLACK = (0,0,0)
BG_TOP = (18,24,45)
BG_BOTTOM = (6,9,20)
YELLOW = (255,215,80)
RED = (220,70,70)
GREEN = (80,220,110)
GOLD = (240,200,60)

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Tower Defense - Optimized Final")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 18)
small_font = pygame.font.SysFont("Arial", 14)

RAND = random.Random()

# -----------------------
# PATHFINDING A*
# -----------------------
def heuristic(a,b): return abs(a[0]-b[0]) + abs(a[1]-b[1])
def neighbors(node, grid):
    x,y = node
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx,ny = x+dx, y+dy
        if 0<=nx<GRID_W and 0<=ny<GRID_H:
            if not grid[ny][nx]:
                yield (nx,ny)

# We'll wrap astar so it can accept the combined_grid passed externally (to use cache)
def astar_on_grid(grid, start, goal):
    if start==goal: return [start]
    open_set = []
    heapq.heappush(open_set, (heuristic(start,goal), 0, start))
    came_from = {}
    cost_so_far = {start:0}
    while open_set:
        _, cost, current = heapq.heappop(open_set)
        if current==goal:
            path=[current]
            while current in came_from:
                current=came_from[current]; path.append(current)
            path.reverse(); return path
        for n in neighbors(current, grid):
            new_cost = cost_so_far[current] + 1
            if n not in cost_so_far or new_cost < cost_so_far[n]:
                cost_so_far[n]=new_cost
                priority = new_cost + heuristic(n,goal)
                heapq.heappush(open_set, (priority, new_cost, n))
                came_from[n]=current
    return None

# -----------------------
# Procedural asset generation (cached)
# -----------------------
def make_tower_sprite(kind):
    s = pygame.Surface((48,48), pygame.SRCALPHA)
    cx,cy = 24,24
    pygame.draw.ellipse(s, (10,10,10,160), (6,26,36,12))
    if kind=='basic': base=(40,60,90); ring=(80,120,180)
    elif kind=='slow': base=(70,40,90); ring=(150,100,200)
    elif kind=='splash': base=(60,80,40); ring=(170,190,80)
    elif kind=='rapid': base=(30,130,140); ring=(100,200,210)
    elif kind=='multi': base=(150,90,30); ring=(220,160,80)
    elif kind=='pierce': base=(140,40,40); ring=(200,80,80)
    elif kind=='ultimate': base=(200,160,40); ring=(255,230,120)
    else: base=(60,60,60); ring=(160,160,160)
    pygame.draw.circle(s, base, (cx,cy), 18)
    pygame.draw.circle(s, ring, (cx,cy), 12)
    if kind=='basic':
        pygame.draw.rect(s, (220,220,240), (cx-3,cy-18,6,12))
    elif kind=='slow':
        pygame.draw.polygon(s, (180,180,255), [(cx,cy-18),(cx-6,cy-6),(cx+6,cy-6)])
    elif kind=='splash':
        pygame.draw.circle(s, (240,240,160), (cx,cy), 6, 2)
    elif kind=='rapid':
        for i in range(-2,3):
            pygame.draw.line(s, (200,240,240), (cx+i*2,cy-14),(cx+i*2,cy-6),2)
    elif kind=='multi':
        for a in (-0.6,0,0.6):
            bx = cx + math.cos(a)*14; by = cy + math.sin(a)*14
            pygame.draw.circle(s,(240,200,160),(int(bx),int(by)),3)
    elif kind=='pierce':
        pygame.draw.line(s,(255,190,190),(cx,cy-18),(cx,cy+6),3)
    elif kind=='ultimate':
        pygame.draw.circle(s,(255,230,120),(cx,cy),8)
        pygame.draw.line(s,(255,200,60),(cx,cy-20),(cx,cy+20),3)
    pygame.draw.circle(s,(20,20,30),(cx,cy),4)
    return s

def make_enemy_sprite(kind):
    s = pygame.Surface((40,40), pygame.SRCALPHA)
    cx,cy=20,20
    if kind=='scout': col=(200,240,120)
    elif kind=='grunt': col=(200,60,60)
    elif kind=='tank': col=(120,120,200)
    elif kind=='sapper': col=(200,120,60)
    else: col=(180,180,180)
    pygame.draw.ellipse(s,(12,12,12,180),(6,24,28,8))
    pygame.draw.circle(s,col,(cx,cy),12)
    pygame.draw.circle(s,(max(0,col[0]-80),max(0,col[1]-40),max(0,col[2]-40)),(cx-4,cy-4),6)
    if kind=='sapper':
        pygame.draw.rect(s, (20,20,20), (cx-6,cy-6,12,4))
    return s

SPRITES = {}
for k in ('basic','slow','splash','rapid','multi','pierce','ultimate'):
    SPRITES['tower_'+k] = make_tower_sprite(k)
for k in ('scout','grunt','tank','sapper'):
    SPRITES['enemy_'+k] = make_enemy_sprite(k)

# -----------------------
# Effects
# -----------------------
class Particle:
    __slots__ = ('x','y','vx','vy','life','age','size','color')
    def __init__(self,x,y):
        self.x=x+RAND.uniform(-6,6); self.y=y+RAND.uniform(-6,6)
        a=RAND.uniform(0,2*math.pi); s=RAND.uniform(1.5,4.0)
        self.vx=math.cos(a)*s; self.vy=math.sin(a)*s
        self.life=RAND.uniform(0.5,1.1); self.age=0
        self.size=RAND.randint(2,4)
        self.color=(RAND.randint(160,255), RAND.randint(80,220), RAND.randint(60,220))
    def update(self,dt):
        self.age += dt; self.x += self.vx*dt*60; self.y += self.vy*dt*60; self.vy += 0.06*dt*60
    def draw(self,surf):
        t = 1 - (self.age/self.life)
        if t <= 0: return
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), max(1, int(self.size * t)))

class DamagePopup:
    __slots__ = ('x','y','text','color','age','life','vy')
    def __init__(self,x,y,text,color=YELLOW):
        self.x=x; self.y=y; self.text=str(text); self.color=color
        self.age=0; self.life=DAMAGE_POPUP_LIFE; self.vy=-1.2
    def update(self,dt):
        self.age += dt; self.y += self.vy*dt*60; self.vy -= 0.03*dt*60
    def draw(self,surf):
        alpha = max(0, int(255*(1-self.age/self.life)))
        txt = small_font.render(self.text, True, self.color)
        txt.set_alpha(alpha)
        surf.blit(txt, (int(self.x - txt.get_width()/2), int(self.y)))

class ScreenShake:
    __slots__ = ('time','duration','mag')
    def __init__(self):
        self.time=0; self.duration=0; self.mag=0
    def start(self,duration,mag):
        self.duration=duration; self.time=duration; self.mag=mag
    def update(self,dt):
        if self.time>0: self.time = max(0, self.time - dt)
    def offset(self):
        if self.time<=0: return (0,0)
        f = self.time/self.duration; amp = self.mag * f
        return (RAND.uniform(-amp, amp), RAND.uniform(-amp, amp))

SHAKE = ScreenShake()

# -----------------------
# Projectile
# -----------------------
class Projectile:
    __slots__ = ('x','y','prev','target','damage','kind','owner_tower','speed','alive','vx','vy','pierce_remaining','hit_ids')
    def __init__(self,x,y,target=None,damage=15,kind='basic',owner_tower=None,vx=None,vy=None,pierce_count=0):
        self.x=x; self.y=y; self.prev=deque(maxlen=6); self.prev.append((x,y))
        self.target=target; self.damage=damage; self.kind=kind; self.owner_tower=owner_tower
        self.speed=PROJECTILE_SPEED; self.alive=True
        if vx is not None and vy is not None:
            d=math.hypot(vx,vy) or 1.0
            self.vx = vx/d; self.vy = vy/d
        else:
            self.vx = None; self.vy = None
        self.pierce_remaining = pierce_count
        self.hit_ids = set()
    def update(self, enemies):
        # localize for speed
        kind = self.kind
        if kind in ('basic','slow','splash'):
            tgt = self.target
            if tgt is None or not getattr(tgt,'alive',False):
                nearest=None; nd=None
                for e in enemies:
                    if not e.alive: continue
                    dx = e.x - self.x; dy = e.y - self.y
                    d2 = dx*dx + dy*dy
                    if nd is None or d2 < nd: nd = d2; nearest = e
                if nearest: self.target = nearest
                else: self.alive=False; return
                tgt = self.target
            dx = tgt.x - self.x; dy = tgt.y - self.y
            dist = math.hypot(dx,dy)
            if dist < 6:
                self.x = tgt.x; self.y = tgt.y
                if kind == 'basic':
                    if tgt.alive: tgt.hp -= self.damage
                elif kind == 'slow':
                    if tgt.alive:
                        tgt.hp -= self.damage
                        st = getattr(self.owner_tower,'slow_time',1.5); sf = getattr(self.owner_tower,'slow_amount',0.5)
                        tgt.apply_slow(sf,st)
                elif kind == 'splash':
                    # handled by Game after projectile removal
                    pass
                self.alive = False; return
            nx = dx / dist; ny = dy / dist
            self.prev.append((self.x,self.y)); self.x += nx*self.speed; self.y += ny*self.speed
        elif kind == 'pierce':
            if self.vx is None or self.vy is None:
                self.alive = False; return
            self.prev.append((self.x,self.y)); self.x += self.vx*self.speed; self.y += self.vy*self.speed
            if self.x < -20 or self.x > SCREEN_W+20 or self.y < -20 or self.y > SCREEN_H+20:
                self.alive = False; return
            for e in enemies:
                if not e.alive: continue
                eid = id(e)
                if eid in self.hit_ids: continue
                dx = e.x - self.x; dy = e.y - self.y
                if dx*dx + dy*dy <= 12*12:
                    e.hp -= self.damage; self.hit_ids.add(eid); self.pierce_remaining -= 1
                    if self.pierce_remaining <= 0:
                        self.alive = False; break
        else:
            # fallback homing
            tgt = self.target
            if tgt is None:
                self.alive = False; return
            dx = tgt.x - self.x; dy = tgt.y - self.y
            dist = math.hypot(dx,dy)
            if dist < 6:
                if tgt.alive: tgt.hp -= self.damage
                self.alive = False; return
            nx = dx/dist; ny = dy/dist
            self.prev.append((self.x,self.y)); self.x += nx*self.speed; self.y += ny*self.speed
    def draw(self, surf):
        pts = list(self.prev) + [(self.x,self.y)]
        # draw simple trail without creating surfaces (faster)
        for i in range(len(pts)-1):
            a = pts[i]; b = pts[i+1]
            width = max(1, 4 - (len(pts)-1 - i)//2)
            pygame.draw.line(surf, (255,200,70), (int(a[0]),int(a[1])), (int(b[0]),int(b[1])), width)
        if self.kind == 'pierce':
            pygame.draw.circle(surf, (255,180,80), (int(self.x), int(self.y)), 5)
            if self.vx is not None:
                pygame.draw.line(surf, (255,220,120), (int(self.x), int(self.y)), (int(self.x + self.vx*6), int(self.y + self.vy*6)), 3)
        elif self.kind == 'splash':
            pygame.draw.circle(surf, (240,120,60), (int(self.x), int(self.y)), 6)
        elif self.kind == 'slow':
            pygame.draw.circle(surf, (160,180,255), (int(self.x), int(self.y)), 5)
        else:
            pygame.draw.circle(surf, YELLOW, (int(self.x), int(self.y)), 5)

# -----------------------
# Tower
# -----------------------
class Tower:
    __slots__ = ('gx','gy','x','y','kind','angle','cooldown','range','rate','damage','hp','max_hp',
                 'sprite','extra')
    def __init__(self,gx,gy,kind='basic'):
        self.gx=gx; self.gy=gy; self.x=gx*TILE_SIZE + TILE_SIZE//2; self.y=gy*TILE_SIZE + TILE_SIZE//2
        self.kind=kind; self.angle=0; self.cooldown=0.0; self.extra = {}
        if kind=='basic': self.range=140; self.rate=0.55; self.damage=22; self.hp=120
        elif kind=='slow': self.range=120; self.rate=0.9; self.damage=10; self.extra['slow_amount']=0.45; self.extra['slow_time']=1.75; self.hp=110
        elif kind=='splash': self.range=130; self.rate=1.15; self.damage=16; self.extra['splash_radius']=44; self.hp=130
        elif kind=='rapid': self.range=120; self.rate=0.18; self.damage=9; self.hp=90
        elif kind=='multi': self.range=150; self.rate=1.0; self.damage=12; self.extra['multi_count']=3; self.extra['spread_deg']=20; self.hp=130
        elif kind=='pierce': self.range=160; self.rate=1.4; self.damage=28; self.extra['pierce_count']=3; self.hp=140
        elif kind=='ultimate': self.range=220; self.rate=4.5; self.damage=180; self.extra['aoe_radius']=100; self.hp=420
        else: self.range=130; self.rate=0.7; self.damage=18; self.hp=120
        self.max_hp = self.hp
        self.sprite = SPRITES.get('tower_'+kind)
    def update(self, dt, enemies, projectiles, game):
        self.cooldown -= dt
        # nearest in range (compare squared distances)
        best = None; bd2 = None; rx = self.range; r2 = rx*rx
        for e in enemies:
            if not e.alive: continue
            dx = e.x - self.x; dy = e.y - self.y; d2 = dx*dx + dy*dy
            if d2 <= r2:
                if bd2 is None or d2 < bd2:
                    bd2 = d2; best = e
        if best:
            desired = math.atan2(best.y - self.y, best.x - self.x)
            diff = (desired - self.angle + math.pi)%(2*math.pi) - math.pi
            self.angle += diff * min(1, dt*8)
        else:
            self.angle += 0.005*dt*60
        if best and self.cooldown <= 0:
            px = self.x + math.cos(self.angle)*12; py = self.y + math.sin(self.angle)*12
            k = self.kind
            if k == 'basic':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='basic',owner_tower=self))
            elif k == 'slow':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='slow',owner_tower=self))
            elif k == 'splash':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='splash',owner_tower=self))
            elif k == 'rapid':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='basic',owner_tower=self))
            elif k == 'multi':
                cnt = self.extra.get('multi_count',3); spread = self.extra.get('spread_deg',20)
                mid = (cnt-1)/2.0
                for i in range(cnt):
                    offset = (i-mid) * math.radians(spread)
                    ang = self.angle + offset; vx = math.cos(ang); vy = math.sin(ang)
                    projectiles.append(Projectile(px,py,target=None,damage=self.damage,kind='basic',owner_tower=self,vx=vx,vy=vy))
            elif k == 'pierce':
                vx = math.cos(self.angle); vy = math.sin(self.angle)
                projectiles.append(Projectile(px,py,target=None,damage=self.damage,kind='pierce',owner_tower=self,vx=vx,vy=vy,pierce_count=self.extra.get('pierce_count',3)))
            elif k == 'ultimate':
                # ultimate: big AOE at target
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='splash',owner_tower=self))
                SHAKE.start(0.25, 6)
            self.cooldown = self.rate
    def draw(self, surf):
        # draw sprite
        surf.blit(self.sprite, (self.x - self.sprite.get_width()/2, self.y - self.sprite.get_height()/2))
        # health bar
        w = 36; h = 6
        bx = self.x - w//2; by = self.y - TILE_SIZE//2 - 10
        pygame.draw.rect(surf, (30,30,30), (bx,by,w,h))
        hp_w = int(w * max(0, self.hp)/max(1, self.max_hp))
        pygame.draw.rect(surf, (60,200,90), (bx,by,hp_w,h))
        if self.kind == 'ultimate':
            pygame.draw.circle(surf, (255,220,100), (int(self.x), int(self.y)), 26, 3)

# -----------------------
# Enemy
# -----------------------
class Enemy:
    TYPE_PROPS = {
        'scout': {'color':(200,240,120),'speed_mult':1.6,'hp_base':40,'reward':6},
        'grunt': {'color':(200,60,60),'speed_mult':1.0,'hp_base':80,'reward':10},
        'tank':  {'color':(120,120,200),'speed_mult':0.6,'hp_base':180,'reward':20},
        'sapper':{'color':(220,150,80),'speed_mult':0.85,'hp_base':100,'reward':14}
    }
    __slots__ = ('kind','path','x','y','base_speed','speed','hp','max_hp','reward','alive','repath_timer','bob_phase','jitter_offset','display_hp','attack_cooldown','attack_rate','attack_damage','attacking_tower','slow_timer','slow_factor')
    def __init__(self,path_pixels,kind='grunt',speed=None,hp=None,reward=None,jitter_offset=None):
        self.kind = kind
        self.path = deque(path_pixels)
        if self.path: self.x,self.y = self.path[0]
        else: self.x,self.y = 0,0
        props = Enemy.TYPE_PROPS.get(kind, Enemy.TYPE_PROPS['grunt'])
        self.base_speed = (speed if speed is not None else 0.9) * props['speed_mult']
        self.speed = self.base_speed
        self.hp = hp if hp is not None else props['hp_base']
        self.max_hp = self.hp
        self.reward = reward if reward is not None else props['reward']
        self.alive = True
        self.repath_timer = 0
        self.bob_phase = RAND.random()*math.pi*2
        self.jitter_offset = jitter_offset or (0,0)
        self.display_hp = self.hp
        self.attack_cooldown = 0.0
        self.attack_rate = 0.9
        self.attack_damage = 30 if kind=='sapper' else 12
        self.attacking_tower = None
        self.slow_timer = 0.0
        self.slow_factor = 1.0
    def apply_slow(self,factor,duration):
        self.slow_factor = min(self.slow_factor, factor)
        self.slow_timer = max(self.slow_timer, duration)
    def update(self, grid, goal_tile, dt, tile_path_func, towers, game):
        if not self.alive: return
        self.bob_phase += dt*3
        bob = math.sin(self.bob_phase) * 3
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0: self.slow_factor = 1.0
        current_speed = self.base_speed * self.slow_factor
        target_tower = None
        if self.kind == 'sapper':
            bd = None
            for t in towers:
                dx = t.x - self.x; dy = t.y - self.y; d2 = dx*dx + dy*dy
                if bd is None or d2 < bd: bd = d2; target_tower = t
        else:
            for t in towers:
                dx = t.x - self.x; dy = t.y - self.y
                if dx*dx + dy*dy < (TILE_SIZE*0.9)**2:
                    target_tower = t; break
        if target_tower:
            tx = target_tower.x; ty = target_tower.y
            dx = tx - self.x; dy = ty - self.y
            dist = math.hypot(dx,dy)
            if dist <= 18:
                self.attack_cooldown -= dt
                if self.attack_cooldown <= 0:
                    target_tower.hp -= self.attack_damage
                    game.popups.append(DamagePopup(target_tower.x, target_tower.y - 8, str(self.attack_damage), RED))
                    SHAKE.start(0.08, 2)
                    self.attack_cooldown = self.attack_rate
                return
            nx = dx / dist; ny = dy / dist
            self.x += nx * current_speed * dt * 60
            self.y += ny * current_speed * dt * 60 + bob * dt * 15
            self.repath_timer += 1
            if self.repath_timer >= ENEMY_REPATH_INTERVAL:
                self.repath_timer = 0
            return
        # follow path to goal
        if not self.path:
            self.alive = False; return
        tx,ty = self.path[0]; tx += self.jitter_offset[0]; ty += self.jitter_offset[1]
        dx = tx - self.x; dy = ty - self.y
        dist = math.hypot(dx,dy)
        if dist < 3:
            self.path.popleft()
            if not self.path:
                self.alive = False; return
            return
        nx = dx / dist; ny = dy / dist
        self.x += nx * current_speed * dt * 60
        self.y += ny * current_speed * dt * 60 + bob * dt * 15
        self.repath_timer += 1
        if self.repath_timer >= ENEMY_REPATH_INTERVAL:
            self.repath_timer = 0
            cx = int(self.x // TILE_SIZE); cy = int(self.y // TILE_SIZE)
            new_tile_path = tile_path_func((cx,cy), goal_tile)
            if new_tile_path:
                pixel_path = [(tx*TILE_SIZE + TILE_SIZE//2, ty*TILE_SIZE + TILE_SIZE//2) for tx,ty in new_tile_path[1:]]
                if pixel_path:
                    jitter = [(RAND.uniform(-6,6), RAND.uniform(-6,6)) for _ in pixel_path]
                    pixel_path = [(p[0]+j[0], p[1]+j[1]) for p,j in zip(pixel_path, jitter)]
                    self.path = deque(pixel_path)
    def draw(self, surf):
        pygame.draw.ellipse(surf,(12,12,12,180),(self.x-14,self.y-8+SHADOW_OFFSET,28,10))
        sprite = SPRITES.get('enemy_'+self.kind)
        surf.blit(sprite, (self.x - sprite.get_width()/2, self.y - sprite.get_height()/2))
        self.display_hp += (self.hp - self.display_hp) * 0.12
        hp_w = (TILE_SIZE-6) * max(0, self.display_hp / max(1, self.max_hp))
        rect_back = pygame.Rect(self.x - (TILE_SIZE-6)/2, self.y - TILE_SIZE//2 - 10, TILE_SIZE-6, 6)
        pygame.draw.rect(surf, (30,30,30), rect_back)
        pygame.draw.rect(surf, (60,200,90), (rect_back.x, rect_back.y, hp_w, rect_back.h))

# -----------------------
# Map & caching layers
# -----------------------
class GameMap:
    def __init__(self):
        self.grid = [ [0 for _ in range(GRID_W)] for __ in range(GRID_H) ]
        for i in range(4,7):
            for j in range(5,8):
                self.grid[j][i] = 1
        for i in range(10,13):
            for j in range(2,5):
                self.grid[j][i] = 1
        for i in range(8,11):
            for j in range(8,11):
                self.grid[j][i] = 1
        self.spawn_tiles = [
            (0, GRID_H//2),
            (0, max(1, GRID_H//3)),
            (0, min(GRID_H-2, 2*GRID_H//3))
        ]
        self.goal_tile = (GRID_W-1, GRID_H//2)
        self.tower_map = [ [0 for _ in range(GRID_W)] for __ in range(GRID_H) ]
        self.tile_noise = [ [RAND.randint(-10,10) for _ in range(GRID_W)] for __ in range(GRID_H) ]
        # pre-render base map surface (tiles + obstacles)
        self.base_surf = pygame.Surface((SCREEN_W, SCREEN_H - 140))
        self._render_base()
    def _render_base(self):
        surf = self.base_surf
        for y in range(GRID_H):
            for x in range(GRID_W):
                rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                base = 72 + self.tile_noise[y][x]
                color = (base+12, base+20, base+30)
                pygame.draw.rect(surf, color, rect)
                if self.grid[y][x] == 1:
                    pygame.draw.rect(surf, (95,95,95), rect.inflate(-6,-6))
                pygame.draw.rect(surf, (12,12,18), rect, 1)
    def set_tower(self,gx,gy,val):
        self.tower_map[gy][gx] = 1 if val else 0
    def get_combined_grid(self):
        combined = [ row[:] for row in self.grid ]
        tm = self.tower_map
        for y in range(GRID_H):
            crow = combined[y]
            trow = tm[y]
            for x in range(GRID_W):
                if trow[x] == 1:
                    crow[x] = 1
        return combined
    def tile_path_to_pixels(self,tile_path,jitter=False):
        res=[]
        for (tx,ty) in tile_path:
            px = tx*TILE_SIZE + TILE_SIZE//2; py = ty*TILE_SIZE + TILE_SIZE//2
            if jitter:
                px += RAND.uniform(-8,8); py += RAND.uniform(-8,8)
            res.append((px,py))
        return res
    def draw(self,surf, tower_map_overlay=None):
        # blit base
        surf.blit(self.base_surf, (0,0))
        # draw tower_map overlay if provided (draw tower tiles)
        if tower_map_overlay is not None:
            for y in range(GRID_H):
                for x in range(GRID_W):
                    if tower_map_overlay[y][x] == 1:
                        rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                        pygame.draw.rect(surf, (30,90,150), rect.inflate(-8,-8))
                        pygame.draw.rect(surf, (12,12,18), rect, 1)
        # spawn and goal
        for s in self.spawn_tiles:
            sx,sy = s
            pygame.draw.rect(surf, (20,180,40),(sx*TILE_SIZE+6, sy*TILE_SIZE+6, TILE_SIZE-12, TILE_SIZE-12))
        gx,gy = self.goal_tile
        pygame.draw.rect(surf,(200,30,30),(gx*TILE_SIZE+6, gy*TILE_SIZE+6, TILE_SIZE-12, TILE_SIZE-12))

# -----------------------
# Game (with caches)
# -----------------------
class Game:
    def __init__(self):
        self.map = GameMap()
        self.towers = []
        self.enemies = []
        self.projectiles = []
        self.particles = []
        self.popups = []
        self.money = START_MONEY
        self.lives = 18
        self.wave = 0
        self.wave_in_progress = False
        self.spawn_queue = []
        self.selected_tower_kind = 'basic'
        # caches
        self._combined_grid = self.map.get_combined_grid()
        self._grid_version = 0
        self._astar_cache = {}  # key: (start,goal,grid_version) -> path
        # pre-render background gradient once
        self._background = pygame.Surface((SCREEN_W, SCREEN_H - 140))
        for y in range(self._background.get_height()):
            t = y / (self._background.get_height() - 1)
            r = int(BG_TOP[0]*(1-t) + BG_BOTTOM[0]*t)
            g = int(BG_TOP[1]*(1-t) + BG_BOTTOM[1]*t)
            b = int(BG_TOP[2]*(1-t) + BG_BOTTOM[2]*t)
            pygame.draw.line(self._background, (r,g,b), (0,y), (SCREEN_W,y))
    def mark_grid_dirty(self):
        # Call when tower_map changes (place/remove tower)
        self._combined_grid = self.map.get_combined_grid()
        self._grid_version += 1
        self._astar_cache.clear()
    def astar_cached(self, start, goal):
        key = (start, goal, self._grid_version)
        if key in self._astar_cache:
            return self._astar_cache[key]
        path = astar_on_grid(self._combined_grid, start, goal)
        self._astar_cache[key] = path
        return path
    def start_wave(self):
        if self.wave_in_progress: return
        self.wave += 1; self.wave_in_progress = True
        count = BASE_WAVE_COUNT + (self.wave - 1) * WAVE_INCREMENT
        interval = max(WAVE_BASE_INTERVAL - (self.wave-1)*2, WAVE_MIN_INTERVAL)
        for i in range(count):
            base = i * interval
            jitter = RAND.randint(0, int(interval*0.6))
            spawn_frames = base + jitter
            t_roll = RAND.random()
            if self.wave <= 2:
                if t_roll < 0.45: kind='scout'
                elif t_roll < 0.9: kind='grunt'
                else: kind='sapper'
            elif self.wave <=5:
                if t_roll < 0.3: kind='scout'
                elif t_roll < 0.75: kind='grunt'
                elif t_roll < 0.9: kind='sapper'
                else: kind='tank'
            else:
                if t_roll < 0.25: kind='scout'
                elif t_roll < 0.6: kind='grunt'
                elif t_roll < 0.9: kind='sapper'
                else: kind='tank'
            props = Enemy.TYPE_PROPS[kind]
            speed = 0.9 + RAND.random()*0.6 + (self.wave-1)*0.02
            hp = int(props['hp_base'] + (self.wave-1)*10 + RAND.randint(-6, 14))
            reward = props['reward'] + (self.wave-1)
            self.spawn_queue.append({'frames':spawn_frames, 'spec':{'kind':kind,'speed':speed,'hp':hp,'reward':reward}})
        self.spawn_queue.sort(key=lambda s: s['frames'])
    def spawn_enemy(self, spec):
        spawn_tile = RAND.choice(self.map.spawn_tiles)
        tile_path = self.astar_cached(spawn_tile, self.map.goal_tile)
        if tile_path is None:
            px_path = [(spawn_tile[0]*TILE_SIZE + TILE_SIZE//2, spawn_tile[1]*TILE_SIZE + TILE_SIZE//2),
                       (self.map.goal_tile[0]*TILE_SIZE + TILE_SIZE//2, self.map.goal_tile[1]*TILE_SIZE + TILE_SIZE//2)]
        else:
            px_path = self.map.tile_path_to_pixels(tile_path, jitter=True)
        jitter_offset = (RAND.uniform(-8,8), RAND.uniform(-6,6))
        e = Enemy(px_path, kind=spec['kind'], speed=spec['speed'], hp=spec['hp'], reward=spec['reward'], jitter_offset=jitter_offset)
        if e.path:
            sx,sy = e.path[0]; e.x = sx + RAND.uniform(-8,8); e.y = sy + RAND.uniform(-6,6)
        self.enemies.append(e)
    def tile_path_from_to(self, start_tile, goal_tile):
        return self.astar_cached(start_tile, goal_tile)
    def update(self, dt):
        # spawn queue update
        if self.wave_in_progress and self.spawn_queue:
            for item in self.spawn_queue: item['frames'] -= 1
            while self.spawn_queue and self.spawn_queue[0]['frames'] <= 0:
                item = self.spawn_queue.pop(0)
                self.spawn_enemy(item['spec'])
        if self.wave_in_progress and not self.spawn_queue and not any(e.alive for e in self.enemies):
            self.wave_in_progress = False
        # towers update
        for t in list(self.towers):
            t.update(dt, self.enemies, self.projectiles, self)
        # projectiles update: build new list to avoid repeated removes
        new_projectiles = []
        for p in self.projectiles:
            p.update(self.enemies)
            if p.alive:
                new_projectiles.append(p)
            else:
                if p.kind == 'splash':
                    tx,ty = p.x,p.y
                    radius = getattr(p.owner_tower, 'extra', {}).get('splash_radius', getattr(p.owner_tower, 'extra', {}).get('aoe_radius', 44))
                    for e in self.enemies:
                        if not e.alive: continue
                        dx = e.x - tx; dy = e.y - ty
                        if dx*dx + dy*dy <= radius*radius:
                            factor = 1 - (math.hypot(dx,dy) / radius) * 0.6
                            dmg = int(p.damage * factor)
                            e.hp -= dmg
                            self.popups.append(DamagePopup(e.x, e.y - 10, str(dmg), YELLOW))
                    self.create_death_effect(tx,ty)
                else:
                    if p.kind in ('basic','slow') and p.target is not None and p.target.alive:
                        self.popups.append(DamagePopup(p.target.x, p.target.y - 10, str(int(p.damage)), YELLOW))
                    else:
                        self.create_hit_effect(p.x,p.y,p.damage)
        self.projectiles = new_projectiles
        # enemies update and tower destruction detection
        for e in list(self.enemies):
            if not e.alive:
                if e.hp <= 0:
                    self.money += e.reward
                    self.create_death_effect(e.x, e.y)
                else:
                    self.lives -= 1
                try: self.enemies.remove(e)
                except ValueError: pass
                continue
            e.update(self._combined_grid, self.map.goal_tile, dt, self.tile_path_from_to, self.towers, self)
        # remove destroyed towers and free cells
        removed_any = False
        for t in list(self.towers):
            if t.hp <= 0:
                self.create_death_effect(t.x, t.y)
                gx,gy = t.gx, t.gy
                self.map.set_tower(gx, gy, False)
                removed_any = True
                try: self.towers.remove(t)
                except ValueError: pass
        if removed_any:
            self.mark_grid_dirty()
        # finalize enemy deaths by hp
        for e in list(self.enemies):
            if e.hp <= 0 and e.alive:
                e.alive = False
        # update particles & popups
        for p in list(self.particles):
            p.update(dt)
            if p.age >= p.life:
                try: self.particles.remove(p)
                except ValueError: pass
        for pop in list(self.popups):
            pop.update(dt)
            if pop.age >= pop.life:
                try: self.popups.remove(pop)
                except ValueError: pass
        SHAKE.update(dt)
        if self.lives <= 0:
            print("Game Over - reiniciando")
            self.reset()
    def reset(self):
        self.__init__()
    def create_death_effect(self,x,y):
        for _ in range(PARTICLE_COUNT):
            self.particles.append(Particle(x,y))
        self.popups.append(DamagePopup(x,y,"+0",GREEN))
        SHAKE.start(0.12, 5)
    def create_hit_effect(self,x,y,damage):
        for _ in range(3):
            self.particles.append(Particle(x,y))
        self.popups.append(DamagePopup(x,y,str(int(damage)),YELLOW))
    def place_tower(self,gx,gy,kind=None):
        if gx<0 or gx>=GRID_W or gy<0 or gy>=GRID_H: return False
        if (gx,gy) in [s for s in self.map.spawn_tiles] or (gx,gy)==self.map.goal_tile: return False
        if self.map.grid[gy][gx]==1: return False
        if self.map.tower_map[gy][gx]==1: return False
        self.map.set_tower(gx,gy,True)
        combined = self.map.get_combined_grid()
        ok=True
        for s in self.map.spawn_tiles:
            if astar_on_grid(combined, s, self.map.goal_tile) is None:
                ok=False; break
        if not ok:
            self.map.set_tower(gx,gy,False); return False
        cost = ULTIMATE_COST if (kind=='ultimate' or (kind is None and self.selected_tower_kind=='ultimate')) else TOWER_COST
        if self.money < cost:
            self.map.set_tower(gx,gy,False); return False
        self.money -= cost
        tk = kind or self.selected_tower_kind
        tw = Tower(gx,gy,kind=tk)
        self.towers.append(tw)
        # mark grid dirty and update combined grid and astar cache
        self.mark_grid_dirty()
        return True
    def draw(self, surf):
        # background + base map + tower overlay
        surf.blit(self._background, (0,0))
        self.map.draw(surf, tower_map_overlay=self.map.tower_map)
        # draw towers
        for t in self.towers:
            t.draw(surf)
        # enemies - painter order
        if len(self.enemies) > 16:
            # only sort if many enemies
            enemies_sorted = sorted(self.enemies, key=lambda en: en.y)
        else:
            enemies_sorted = self.enemies
        for e in enemies_sorted:
            e.draw(surf)
        # projectiles
        for p in self.projectiles:
            p.draw(surf)
        # particles & popups
        for part in self.particles: part.draw(surf)
        for pop in self.popups: pop.draw(surf)
        # HUD
        hud_rect = pygame.Rect(0, SCREEN_H-140, SCREEN_W, 140)
        pygame.draw.rect(surf, (12,12,16), hud_rect)
        pygame.draw.line(surf, (40,40,60), (0, SCREEN_H-140), (SCREEN_W, SCREEN_H-140), 2)
        draw_text(surf, f"Dinero: ${self.money}", 12, SCREEN_H-132)
        draw_text(surf, f"Vidas: {self.lives}", 12, SCREEN_H-102)
        draw_text(surf, f"Oleada: {self.wave}", 12, SCREEN_H-72)
        draw_text(surf, f"Coste torre: ${TOWER_COST}   Ultimate: ${ULTIMATE_COST}", 260, SCREEN_H-132)
        draw_text(surf, "SPACE: iniciar oleada    1-7: seleccionar torreta    Clic izquierdo: colocar", 260, SCREEN_H-102)
        types = [('1','Basic'),('2','Slow'),('3','Splash'),('4','Rapid'),('5','Multi'),('6','Pierce'),('7','Ultimate')]
        x0 = SCREEN_W - 480; y0 = SCREEN_H - 132
        for i,(k,label) in enumerate(types):
            col = WHITE if self.selected_tower_kind==label.lower() else (180,180,180)
            draw_small_text(surf, f"{k}:{label}", x0 + i*68, y0, col)
        # preview placement
        mx,my = pygame.mouse.get_pos()
        gx = mx // TILE_SIZE; gy = my // TILE_SIZE
        if my < GRID_H * TILE_SIZE:
            rect = pygame.Rect(gx*TILE_SIZE+6, gy*TILE_SIZE+6, TILE_SIZE-12, TILE_SIZE-12)
            can = self.can_place_preview(gx,gy)
            color_ok=(40,200,100); color_no=(200,60,60)
            s = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA); s.fill((* (color_ok if can else color_no), 100))
            surf.blit(s, (rect.x, rect.y))
    def can_place_preview(self,gx,gy):
        if gx<0 or gx>=GRID_W or gy<0 or gy>=GRID_H: return False
        if (gx,gy) in [s for s in self.map.spawn_tiles] or (gx,gy)==self.map.goal_tile: return False
        if self.map.grid[gy][gx]==1: return False
        if self.map.tower_map[gy][gx]==1: return False
        self.map.set_tower(gx,gy,True)
        ok=True
        for s in self.map.spawn_tiles:
            if astar_on_grid(self.map.get_combined_grid(), s, self.map.goal_tile) is None:
                ok=False; break
        self.map.set_tower(gx,gy,False)
        return ok

# helper draw functions
def draw_text(surf,text,x,y,color=WHITE):
    img = font.render(text,True,color); surf.blit(img,(x,y))
def draw_small_text(surf,text,x,y,color=WHITE):
    img = small_font.render(text,True,color); surf.blit(img,(x,y))

# -----------------------
# MAIN LOOP
# -----------------------
def main():
    game = Game()
    running = True
    while running:
        dt = clock.tick(FPS)/1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running=False; break
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running=False; break
                if event.key == pygame.K_SPACE: game.start_wave()
                if event.key == pygame.K_1: game.selected_tower_kind='basic'
                if event.key == pygame.K_2: game.selected_tower_kind='slow'
                if event.key == pygame.K_3: game.selected_tower_kind='splash'
                if event.key == pygame.K_4: game.selected_tower_kind='rapid'
                if event.key == pygame.K_5: game.selected_tower_kind='multi'
                if event.key == pygame.K_6: game.selected_tower_kind='pierce'
                if event.key == pygame.K_7: game.selected_tower_kind='ultimate'
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    mx,my = pygame.mouse.get_pos()
                    if my < GRID_H * TILE_SIZE:
                        gx = mx // TILE_SIZE; gy = my // TILE_SIZE
                        placed = game.place_tower(gx, gy, kind=game.selected_tower_kind)
                        if not placed:
                            game.popups.append(DamagePopup(mx, my-10, "No se puede colocar", RED))
        game.update(dt)
        off = SHAKE.offset()
        screen.fill(BLACK)
        temp = pygame.Surface((SCREEN_W, SCREEN_H))
        game.draw(temp)
        screen.blit(temp, (int(off[0]), int(off[1])))
        pygame.display.flip()
    pygame.quit(); sys.exit()

if __name__ == "__main__":
    main()
