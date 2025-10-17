import pygame, math
from collections import deque
from config import RAND, TILE_SIZE, MAP_W_PX, MAP_H_PX, PROJECTILE_SPEED, SHADOW_OFFSET, DAMAGE_POPUP_LIFE, TOWER_DEFS
from sprites import SPRITES
from config import WHITE, YELLOW, RED, GREEN

class Particle:
    __slots__ = ('x','y','vx','vy','life','age','size','color')
    def __init__(self,x,y):
        self.x=x+RAND.uniform(-6,6); self.y=y+RAND.uniform(-6,6)
        a = RAND.uniform(0,2*math.pi); s = RAND.uniform(1.6,4.0)
        self.vx = math.cos(a)*s; self.vy = math.sin(a)*s
        self.life = RAND.uniform(0.5,1.1); self.age = 0
        self.size = RAND.randint(2,4)
        self.color = (RAND.randint(160,255), RAND.randint(90,220), RAND.randint(60,220))
    def update(self,dt):
        self.age += dt; self.x += self.vx*dt*60; self.y += self.vy*dt*60; self.vy += 0.06*dt*60
    def draw(self,surf):
        t = 1 - (self.age/self.life)
        if t <= 0: return
        r = max(1, int(self.size * t))
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)

class DamagePopup:
    __slots__ = ('x','y','text','color','age','life','vy')
    def __init__(self,x,y,text,color=YELLOW):
        self.x=x; self.y=y; self.text=str(text); self.color=color
        self.age=0; self.life=DAMAGE_POPUP_LIFE; self.vy=-1.2
    def update(self,dt):
        self.age += dt; self.y += self.vy*dt*60; self.vy -= 0.03*dt*60
    def draw(self, surf, font):
        alpha = max(0, int(255*(1-self.age/self.life)))
        txt = font.render(self.text, True, self.color)
        txt.set_alpha(alpha)
        surf.blit(txt, (int(self.x - txt.get_width()/2), int(self.y)))

class MuzzleFlash:
    __slots__ = ('x','y','age','life','radius','color')
    def __init__(self,x,y,color=(255,220,100),radius=12,life=0.12):
        self.x = x; self.y = y; self.age = 0.0; self.life = life
        self.radius = radius; self.color = color
    def update(self,dt):
        self.age += dt
    def draw(self,surf):
        t = max(0, 1 - (self.age / self.life))
        if t <= 0: return
        a = int(255 * t)
        col = (self.color[0], self.color[1], self.color[2], a)
        s = pygame.Surface((self.radius*2, self.radius*2), pygame.SRCALPHA)
        pygame.draw.circle(s, col, (self.radius, self.radius), int(self.radius * t))
        surf.blit(s, (int(self.x - self.radius), int(self.y - self.radius)), special_flags=pygame.BLEND_ADD)

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

class Projectile:
    __slots__ = ('x','y','prev','target','damage','kind','owner_tower','speed','alive','vx','vy','pierce_remaining','hit_ids')
    def __init__(self,x,y,target=None,damage=15,kind='basic',owner_tower=None,vx=None,vy=None,pierce_count=0):
        self.x=x; self.y=y; self.prev=deque(maxlen=8); self.prev.append((x,y))
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
        kind = self.kind
        if kind == 'straight':
            if self.vx is None or self.vy is None:
                self.alive=False; return
            self.prev.append((self.x,self.y)); self.x += self.vx*self.speed; self.y += self.vy*self.speed
            if self.x < -20 or self.x > MAP_W_PX+20 or self.y < -20 or self.y > MAP_H_PX+20:
                self.alive=False; return
            for e in enemies:
                if not e.alive: continue
                dx = e.x - self.x; dy = e.y - self.y
                if dx*dx + dy*dy <= 12*12:
                    e.hp -= self.damage
                    self.alive = False
                    break
            return
        if kind in ('basic','slow','splash'):
            tgt = self.target
            if tgt is None or not getattr(tgt,'alive',False):
                nearest=None; nd=None
                for e in enemies:
                    if not e.alive: continue
                    dx = e.x - self.x; dy = e.y - self.y; d2 = dx*dx + dy*dy
                    if nd is None or d2 < nd: nd = d2; nearest = e
                if nearest: self.target = nearest; tgt = nearest
                else: self.alive=False; return
            dx = tgt.x - self.x; dy = tgt.y - self.y
            dist = math.hypot(dx,dy)
            if dist < 6:
                self.x = tgt.x; self.y = tgt.y
                if kind == 'basic':
                    if tgt.alive: tgt.hp -= self.damage
                elif kind == 'slow':
                    if tgt.alive:
                        tgt.hp -= self.damage
                        st = getattr(self.owner_tower,'extra',{}).get('slow_time',1.5)
                        sf = getattr(self.owner_tower,'extra',{}).get('slow_amount',0.5)
                        tgt.apply_slow(sf,st)
                elif kind == 'splash':
                    pass
                self.alive=False; return
            nx = dx/dist; ny = dy/dist
            self.prev.append((self.x,self.y)); self.x += nx*self.speed; self.y += ny*self.speed
        elif kind == 'pierce':
            if self.vx is None or self.vy is None:
                self.alive=False; return
            self.prev.append((self.x,self.y)); self.x += self.vx*self.speed; self.y += self.vy*self.speed
            if self.x < -20 or self.x > MAP_W_PX+20 or self.y < -20 or self.y > MAP_H_PX+20:
                self.alive=False; return
            for e in enemies:
                if not e.alive: continue
                eid = id(e)
                if eid in self.hit_ids: continue
                dx = e.x - self.x; dy = e.y - self.y
                if dx*dx + dy*dy <= 12*12:
                    e.hp -= self.damage; self.hit_ids.add(eid); self.pierce_remaining -= 1
                    if self.pierce_remaining <= 0:
                        self.alive=False; break
        else:
            tgt = self.target
            if tgt is None: self.alive=False; return
            dx = tgt.x - self.x; dy = tgt.y - self.y
            dist = math.hypot(dx,dy)
            if dist < 6:
                if tgt.alive: tgt.hp -= self.damage
                self.alive=False; return
            nx = dx/dist; ny = dy/dist
            self.prev.append((self.x,self.y)); self.x += nx*self.speed; self.y += ny*self.speed
    def draw(self,surf):
        pts = list(self.prev) + [(self.x,self.y)]
        for i in range(len(pts)-1):
            a = pts[i]; b = pts[i+1]
            width = max(1, 4 - (len(pts)-1 - i)//2)
            col = (255,200,70)
            if self.kind == 'pierce': col = (255,160,100)
            elif self.kind == 'slow': col = (160,180,255)
            elif self.kind == 'splash': col = (240,120,60)
            pygame.draw.line(surf, col, (int(a[0]),int(a[1])), (int(b[0]),int(b[1])), width)
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

class Tower:
    __slots__ = ('gx','gy','x','y','kind','angle','cooldown','range','rate','damage','hp','max_hp','sprite','extra','recoil')
    def __init__(self,gx,gy,kind='basic'):
        self.gx=gx; self.gy=gy; self.x=gx*TILE_SIZE + TILE_SIZE//2; self.y=gy*TILE_SIZE + TILE_SIZE//2
        self.kind=kind; self.angle=0; self.cooldown=0.0; self.extra = {}
        defs = TOWER_DEFS.get(kind, {})
        self.range = defs.get('range', 130)
        self.rate = defs.get('rate', 0.7)
        self.damage = defs.get('damage', 18)
        self.hp = defs.get('hp', 120)
        for k,v in defs.items():
            if k not in ('range','rate','damage','hp'):
                self.extra[k] = v
        self.max_hp = self.hp
        self.sprite = SPRITES.get('tower_'+kind)
        self.recoil = 0.0
    def update(self, dt, enemies, projectiles, game):
        self.cooldown -= dt
        if self.recoil > 0:
            self.recoil = max(0.0, self.recoil - dt * 3.5)
        best=None; bd2=None; r2 = self.range * self.range
        for e in enemies:
            if not e.alive: continue
            dx = e.x - self.x; dy = e.y - self.y; d2 = dx*dx + dy*dy
            if d2 <= r2:
                if bd2 is None or d2 < bd2: bd2 = d2; best = e
        if best:
            desired = math.atan2(best.y - self.y, best.x - self.x)
            diff = (desired - self.angle + math.pi) % (2*math.pi) - math.pi
            self.angle += diff * min(1, dt*8)
        else:
            self.angle += 0.005 * dt * 60
        if best and self.cooldown <= 0:
            px = self.x + math.cos(self.angle)*14; py = self.y + math.sin(self.angle)*14
            k = self.kind
            if k == 'basic':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='basic',owner_tower=self))
                self.recoil = max(self.recoil, 0.7)
                game.muzzle_flashes.append(MuzzleFlash(px, py, color=(255,220,120), radius=10, life=0.10))
            elif k == 'slow':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='slow',owner_tower=self))
                self.recoil = max(self.recoil, 0.5)
                game.muzzle_flashes.append(MuzzleFlash(px, py, color=(160,180,255), radius=9, life=0.09))
            elif k == 'splash':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='splash',owner_tower=self))
                self.recoil = max(self.recoil, 0.85)
                game.muzzle_flashes.append(MuzzleFlash(px, py, color=(255,180,100), radius=14, life=0.14))
            elif k == 'rapid':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='basic',owner_tower=self))
                self.recoil = max(self.recoil, 0.35)
                game.muzzle_flashes.append(MuzzleFlash(px, py, color=(255,220,200), radius=8, life=0.06))
            elif k == 'multi':
                cnt = self.extra.get('multi_count',3); spread = self.extra.get('spread_deg',20)
                mid = (cnt-1)/2.0
                for i in range(cnt):
                    offset = (i-mid) * math.radians(spread)
                    ang = self.angle + offset; vx = math.cos(ang); vy = math.sin(ang)
                    projectiles.append(Projectile(px,py,target=None,damage=self.damage,kind='straight',owner_tower=self,vx=vx,vy=vy))
                self.recoil = max(self.recoil, 0.9)
                game.muzzle_flashes.append(MuzzleFlash(px, py, color=(240,200,160), radius=12, life=0.12))
            elif k == 'pierce':
                vx = math.cos(self.angle); vy = math.sin(self.angle)
                projectiles.append(Projectile(px,py,target=None,damage=self.damage,kind='pierce',owner_tower=self,vx=vx,vy=vy,pierce_count=self.extra.get('pierce_count',3)))
                self.recoil = max(self.recoil, 0.95)
                game.muzzle_flashes.append(MuzzleFlash(px, py, color=(255,180,180), radius=12, life=0.11))
            elif k == 'ultimate':
                projectiles.append(Projectile(px,py,target=best,damage=self.damage,kind='splash',owner_tower=self))
                SHAKE.start(0.25, 6)
                self.recoil = max(self.recoil, 1.2)
                game.muzzle_flashes.append(MuzzleFlash(px, py, color=(255,230,120), radius=20, life=0.18))
            self.cooldown = self.rate
    def draw(self, surf):
        surf.blit(self.sprite, (int(self.x - self.sprite.get_width()/2), int(self.y - self.sprite.get_height()/2)))
        riv_offs = [(-14,-6),(14,-6),(-12,8),(12,8)]
        for ox,oy in riv_offs:
            pygame.draw.circle(surf, (30,30,36), (int(self.x+ox*0.6), int(self.y+oy*0.6)), 2)
        bx = self.x + math.cos(self.angle)
        by = self.y + math.sin(self.angle)
        recoil_amount = self.recoil * 6.0
        start_x = self.x - math.cos(self.angle) * recoil_amount
        start_y = self.y - math.sin(self.angle) * recoil_amount
        def barrel_end(length, angle_offset=0.0):
            return (start_x + math.cos(self.angle + angle_offset) * length, start_y + math.sin(self.angle + angle_offset) * length)
        if self.kind == 'basic':
            barrel_len = 20
            ex,ey = barrel_end(barrel_len)
            pygame.draw.line(surf, (230,230,230), (int(start_x), int(start_y)), (int(ex), int(ey)), 6)
            pygame.draw.circle(surf, (200,200,200), (int(ex), int(ey)), 4)
        elif self.kind == 'rapid':
            barrel_len = 18
            for i in range(3):
                off = -2 + i*2
                ex,ey = barrel_end(barrel_len + off)
                pygame.draw.line(surf, (200,240,240), (int(start_x), int(start_y)), (int(ex), int(ey)), 3)
        elif self.kind == 'multi':
            barrel_len = 18
            cnt = self.extra.get('multi_count',3)
            spread = math.radians(self.extra.get('spread_deg',20))
            mid = (cnt-1)/2.0
            for i in range(cnt):
                offset = (i-mid) * spread
                ex,ey = barrel_end(barrel_len, offset)
                pygame.draw.line(surf, (230,200,160), (int(start_x), int(start_y)), (int(ex), int(ey)), 4)
        elif self.kind == 'pierce':
            barrel_len = 26
            ex,ey = barrel_end(barrel_len)
            pygame.draw.line(surf, (255,190,190), (int(start_x), int(start_y)), (int(ex), int(ey)), 5)
            midx,midy = barrel_end(10)
            pygame.draw.line(surf, (255,220,120), (int(midx), int(midy)), (int(ex), int(ey)), 2)
        elif self.kind == 'splash' or self.kind == 'splash':
            barrel_len = 16
            ex,ey = barrel_end(barrel_len)
            pygame.draw.line(surf, (240,180,120), (int(start_x), int(start_y)), (int(ex), int(ey)), 7)
            pygame.draw.circle(surf, (240,120,60), (int(ex), int(ey)), 6, 2)
        elif self.kind == 'slow':
            barrel_len = 16
            ex,ey = barrel_end(barrel_len)
            pygame.draw.line(surf, (160,180,255), (int(start_x), int(start_y)), (int(ex), int(ey)), 5)
        elif self.kind == 'ultimate':
            barrel_len = 28
            ex,ey = barrel_end(barrel_len)
            pygame.draw.line(surf, (255,230,120), (int(start_x), int(start_y)), (int(ex), int(ey)), 8)
            pygame.draw.circle(surf, (255,200,60), (int(ex), int(ey)), 6)
        else:
            barrel_len = 18
            ex,ey = barrel_end(barrel_len)
            pygame.draw.line(surf, (230,230,230), (int(start_x), int(start_y)), (int(ex), int(ey)), 4)
        w = 40; h = 7
        bx = int(self.x - w//2); by = int(self.y - TILE_SIZE//2 - 12)
        pygame.draw.rect(surf, (30,30,30), (bx,by,w,h))
        hp_w = int(w * max(0, self.hp)/max(1, self.max_hp))
        pygame.draw.rect(surf, (60,200,90), (bx,by,hp_w,h))
        if self.kind == 'ultimate':
            pygame.draw.circle(surf, (255,220,100), (int(self.x), int(self.y)), 28, 3)

class Enemy:
    TYPE_PROPS = {
        'scout': {'color':(200,240,120),'speed_mult':1.6,'hp_base':40,'reward':6},
        'grunt': {'color':(200,60,60),'speed_mult':1.0,'hp_base':80,'reward':10},
        'tank' : {'color':(120,120,200),'speed_mult':0.6,'hp_base':180,'reward':20},
        'sapper':{'color':(220,150,80),'speed_mult':0.85,'hp_base':100,'reward':14}
    }
    __slots__ = ('kind','path','x','y','base_speed','speed','hp','max_hp','reward','alive','repath_timer','bob_phase','jitter_offset','display_hp','attack_cooldown','attack_rate','attack_damage','attacking_tower','slow_timer','slow_factor')
    def __init__(self,path_pixels,kind='grunt',speed=None,hp=None,reward=None,jitter_offset=None):
        self.kind=kind; self.path=deque(path_pixels)
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
        self.bob_phase += dt * 3
        bob = math.sin(self.bob_phase) * 3
        if self.slow_timer > 0:
            self.slow_timer -= dt
            if self.slow_timer <= 0: self.slow_factor = 1.0
        current_speed = self.base_speed * self.slow_factor
        target_tower = None
        if self.kind == 'sapper':
            bd=None
            for t in towers:
                dx = t.x - self.x; dy = t.y - self.y; d2 = dx*dx + dy*dy
                if bd is None or d2 < bd: bd=d2; target_tower = t
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
            if self.repath_timer >= 36:
                self.repath_timer = 0
            return
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
        if self.repath_timer >= 36:
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
        pygame.draw.ellipse(surf, (8,8,8,200), (self.x-20, self.y-10+SHADOW_OFFSET, 40, 14))
        tint_col = Enemy.TYPE_PROPS.get(self.kind, {}).get('color', (180,180,180))
        tint = pygame.Surface((48,48), pygame.SRCALPHA)
        tc = (min(255,tint_col[0]+20), min(255,tint_col[1]+20), min(255,tint_col[2]+20), 60)
        pygame.draw.circle(tint, tc, (24,24), 20)
        surf.blit(tint, (int(self.x - 24), int(self.y - 24)), special_flags=pygame.BLEND_RGBA_ADD)
        sprite = SPRITES.get('enemy_'+self.kind)
        surf.blit(sprite, (int(self.x - sprite.get_width()/2), int(self.y - sprite.get_height()/2)))
        for i in range(2):
            rx = int(self.x + RAND.randint(-6,6)); ry = int(self.y + RAND.randint(-6,2))
            pygame.draw.circle(surf, (0,0,0,24), (rx,ry), 1)
        self.display_hp += (self.hp - self.display_hp) * 0.12
        hp_w = (TILE_SIZE-8) * max(0, self.display_hp / max(1, self.max_hp))
        rect_back = pygame.Rect(self.x - (TILE_SIZE-8)/2, self.y - TILE_SIZE//2 - 10, TILE_SIZE-8, 6)
        pygame.draw.rect(surf, (20,20,20), rect_back)
        pygame.draw.rect(surf, (60,200,90), (rect_back.x, rect_back.y, hp_w, rect_back.h))
