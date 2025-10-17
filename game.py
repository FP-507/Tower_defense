import pygame, sys, math
from config import *
from gamemap import GameMap, astar_on_grid
from sprites import SPRITES
from entities import Particle, DamagePopup, MuzzleFlash, ScreenShake, Projectile, Tower, Enemy, SHAKE

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Tower Defense — Modularized")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 18)
font_bold = pygame.font.SysFont("Arial", 20, bold=True)
small_font = pygame.font.SysFont("Arial", 14)

class Game:
    def __init__(self):
        self.map = GameMap()
        self.towers = []
        self.enemies = []
        self.projectiles = []
        self.particles = []
        self.muzzle_flashes = []
        self.popups = []
        self.money = START_MONEY
        self.lives = 18
        self.wave = 0
        self.wave_in_progress = False
        self.spawn_queue = []
        self.selected_tower_kind = 'basic'
        self._combined_grid = self.map.get_combined_grid()
        self._grid_version = 0
        self._astar_cache = {}
        self._background = pygame.Surface((MAP_W_PX, MAP_H_PX))
        for y in range(self._background.get_height()):
            t = y / (self._background.get_height()-1)
            r = int(BG_TOP[0]*(1-t) + BG_BOTTOM[0]*t)
            g = int(BG_TOP[1]*(1-t) + BG_BOTTOM[1]*t)
            b = int(BG_TOP[2]*(1-t) + BG_BOTTOM[2]*t)
            pygame.draw.line(self._background, (r,g,b), (0,y), (MAP_W_PX,y))
    def mark_grid_dirty(self):
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
        interval = max(WAVE_BASE_INTERVAL - (self.wave-1)*1, WAVE_MIN_INTERVAL)
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
            speed = 0.85 + RAND.random()*0.5 + (self.wave-1)*0.02
            hp = int(props['hp_base'] + int((self.wave-1)*8) + RAND.randint(-4, 10))
            reward = max(1, props['reward'] + (self.wave-1)//2)
            self.spawn_queue.append({'frames':spawn_frames, 'spec':{'kind':kind,'speed':speed,'hp':hp,'reward':reward}})
        self.spawn_queue.sort(key=lambda s: s['frames'])
    def spawn_enemy(self,spec):
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
        if self.wave_in_progress and self.spawn_queue:
            for item in self.spawn_queue: item['frames'] -= 1
            while self.spawn_queue and self.spawn_queue[0]['frames'] <= 0:
                item = self.spawn_queue.pop(0)
                self.spawn_enemy(item['spec'])
        if self.wave_in_progress and not self.spawn_queue and not any(e.alive for e in self.enemies):
            self.wave_in_progress = False
        for t in list(self.towers):
            t.update(dt, self.enemies, self.projectiles, self)
        new_projectiles = []
        for p in self.projectiles:
            p.update(self.enemies)
            if p.alive:
                new_projectiles.append(p)
            else:
                if p.kind == 'splash':
                    tx,ty = p.x,p.y
                    radius = getattr(p.owner_tower,'extra',{}).get('splash_radius', getattr(p.owner_tower,'extra',{}).get('aoe_radius', 44))
                    r2 = radius*radius
                    for e in self.enemies:
                        if not e.alive: continue
                        dx = e.x - tx; dy = e.y - ty
                        if dx*dx + dy*dy <= r2:
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
        for mf in list(self.muzzle_flashes):
            mf.update(dt)
            if mf.age >= mf.life:
                try: self.muzzle_flashes.remove(mf)
                except ValueError: pass
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
        for e in list(self.enemies):
            if e.hp <= 0 and e.alive:
                e.alive = False
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
        self.mark_grid_dirty()
        return True
    def draw(self, surf):
        surf.blit(self._background, (0,0))
        path_tiles = self.tile_path_from_to(self.map.spawn_tiles[0], self.map.goal_tile)
        self.map.draw(surf, tower_map_overlay=self.map.tower_map, path_tiles=path_tiles)
        for t in self.towers: t.draw(surf)
        enemies_sorted = sorted(self.enemies, key=lambda en: en.y) if len(self.enemies) > 16 else self.enemies
        for e in enemies_sorted: e.draw(surf)
        for p in self.projectiles: p.draw(surf)
        for part in self.particles: part.draw(surf)
        for mf in self.muzzle_flashes: mf.draw(surf)
        for pop in self.popups: pop.draw(surf, small_font)
        # New HUD: translucent bar, centered hotbar, concise info panel
        hud = pygame.Surface((SCREEN_W, HUD_HEIGHT), pygame.SRCALPHA)
        hud.fill((12,14,18,220))
        # top separator
        pygame.draw.line(hud, (60,60,72), (12, 8), (SCREEN_W-12, 8), 2)
        # shadow under HUD
        shadow = pygame.Surface((SCREEN_W, 10), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0,0,0,150), (0,0, SCREEN_W, 10), border_radius=6)
        surf.blit(shadow, (0, MAP_H_PX))
        surf.blit(hud, (0, MAP_H_PX))

        # LEFT: status card with resources and controls
        left_w = 220
        left_h = HUD_HEIGHT - 28
        left_x = 12; left_y = MAP_H_PX + 12
        left_rect = pygame.Rect(left_x, left_y, left_w, left_h)
        pygame.draw.rect(surf, (24,24,30), left_rect, border_radius=10)
        pygame.draw.rect(surf, (70,70,86), left_rect, width=1, border_radius=10)
        draw_text(surf, "RECURSOS", left_x + 12, left_y + 8, color=(200,200,200))
        draw_text(surf, f"${self.money}", left_x + 12, left_y + 30, color=GOLD, bold=True)
        draw_small_text(surf, f"Vidas: {self.lives}", left_x + 12, left_y + 58, color=(200,200,200))
        draw_small_text(surf, f"Oleada: {self.wave}", left_x + 12, left_y + 80, color=(200,200,200))
        # Wave control
        btn_w = 128; btn_h = 30
        btn_x = left_x + 12; btn_y = left_y + left_h - btn_h - 10
        pygame.draw.rect(surf, (80,160,220), (btn_x, btn_y, btn_w, btn_h), border_radius=8)
        draw_text(surf, "Iniciar Oleada (Space)", btn_x + 8, btn_y + 6, color=(16,16,20), bold=True)

        # CENTER: hotbar in two rows
        kinds = ['basic','slow','splash','rapid','multi','pierce','ultimate']
        cols = 4
        slot_w = 72; slot_h = 84; gap = 10
        hotbar_total_w = cols*slot_w + (cols-1)*gap
        hotbar_x = (SCREEN_W - hotbar_total_w)//2
        # center hotbar vertically within HUD
        hotbar_rows = 2
        total_hotbar_h = hotbar_rows * slot_h + (hotbar_rows-1) * 8
        hotbar_y = MAP_H_PX + (HUD_HEIGHT - total_hotbar_h)//2 - 6
        mx,my = pygame.mouse.get_pos()
        hover_idx = None
        for idx,k in enumerate(kinds):
            row = 0 if idx < cols else 1
            col = idx % cols
            bx = hotbar_x + col*(slot_w + gap)
            by = hotbar_y + row*(slot_h + 8)
            rect = pygame.Rect(bx, by, slot_w, slot_h)
            is_sel = (self.selected_tower_kind == k)
            is_hover = rect.collidepoint(mx,my)
            bg_col = (44,44,52) if not is_sel else (70,90,140)
            pygame.draw.rect(surf, bg_col, rect, border_radius=10)
            pygame.draw.rect(surf, (80,80,96), rect, width=1, border_radius=10)
            sp = SPRITES.get('tower_'+k)
            if sp:
                sp_s = pygame.transform.smoothscale(sp, (56,56))
                surf.blit(sp_s, (bx + (slot_w-sp_s.get_width())//2, by + 8))
            draw_small_text(surf, str(idx+1), bx+6, by+slot_h-18, color=(220,220,220))
            draw_small_text(surf, k, bx+20, by+slot_h-18, color=(200,200,200))
            cost = ULTIMATE_COST if k=='ultimate' else TOWER_COST
            badge_col = (220,180,60) if k=='ultimate' else (80,200,100)
            pygame.draw.circle(surf, badge_col, (bx + slot_w - 18, by + 12), 12)
            draw_small_text(surf, f"${cost}", bx + slot_w - 36, by + 6, color=(20,20,20))
            if is_hover:
                hover_idx = idx

        # RIGHT: info & upgrades
        info_w = 260
        info_x = SCREEN_W - info_w - 12
        info_y = MAP_H_PX + 12
        info_rect = pygame.Rect(info_x, info_y, info_w, HUD_HEIGHT - 24)
        pygame.draw.rect(surf, (24,24,30), info_rect, border_radius=10)
        pygame.draw.rect(surf, (70,70,86), info_rect, width=1, border_radius=10)
        draw_text(surf, "Seleccionada", info_x + 12, info_y + 8, color=(200,200,200))
        draw_text(surf, self.selected_tower_kind.capitalize(), info_x + 12, info_y + 34, color=WHITE, bold=True)
        sps = SPRITES.get('tower_'+self.selected_tower_kind)
        if sps:
            s_s = pygame.transform.smoothscale(sps, (64,64))
            surf.blit(s_s, (info_x + info_rect.w - s_s.get_width() - 12, info_y + 12))
        defs = TOWER_DEFS.get(self.selected_tower_kind, {})
        draw_small_text(surf, f"Daño: {defs.get('damage','-')}", info_x + 12, info_y + 64, color=(200,200,200))
        draw_small_text(surf, f"Cadencia: {defs.get('rate','-')}", info_x + 12, info_y + 82, color=(200,200,200))
        draw_small_text(surf, f"Rango: {defs.get('range','-')}", info_x + 12, info_y + 98, color=(200,200,200))
        # upgrade buttons
        up_w = 100; up_h = 28
        pygame.draw.rect(surf, (200,160,80), (info_x + 12, info_y + info_rect.h - up_h - 10, up_w, up_h), border_radius=6)
        draw_text(surf, "Mejorar", info_x + 18, info_y + info_rect.h - up_h - 6, color=(16,16,20), bold=True)
        pygame.draw.rect(surf, (180,80,80), (info_x + 12 + up_w + 10, info_y + info_rect.h - up_h - 10, up_w, up_h), border_radius=6)
        draw_text(surf, "Vender", info_x + 18 + up_w + 10, info_y + info_rect.h - up_h - 6, color=(16,16,20), bold=True)
        if hover_idx is not None:
            hk = kinds[hover_idx]
            hdefs = TOWER_DEFS.get(hk, {})
            tip_w, tip_h = 220, 86
            tip_x = min(SCREEN_W - tip_w - 12, mx + 12)
            tip_y = MAP_H_PX + 12
            tip_rect = pygame.Rect(tip_x, tip_y, tip_w, tip_h)
            pygame.draw.rect(surf, (18,18,22), tip_rect, border_radius=8)
            pygame.draw.rect(surf, (60,60,72), tip_rect, width=1, border_radius=8)
            draw_text(surf, hk.capitalize(), tip_x + 10, tip_y + 8, color=WHITE, bold=True)
            draw_small_text(surf, f"Daño: {hdefs.get('damage','-')}   Cadencia: {hdefs.get('rate','-')}", tip_x + 10, tip_y + 34, color=(200,200,200))
            draw_small_text(surf, f"Rango: {hdefs.get('range','-')}", tip_x + 10, tip_y + 54, color=(200,200,200))

        # placement preview (unchanged)
        kinds_mouse = kinds
        gx = mx // TILE_SIZE; gy = my // TILE_SIZE
        if my < MAP_H_PX:
            rect = pygame.Rect(gx*TILE_SIZE+6, gy*TILE_SIZE+6, TILE_SIZE-12, TILE_SIZE-12)
            can = self.can_place_preview(gx,gy)
            c = (40,200,100,110) if can else (200,60,60,110)
            overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            overlay.fill(c)
            surf.blit(overlay, (rect.x, rect.y))
            kind = self.selected_tower_kind
            defs = TOWER_DEFS.get(kind)
            if defs:
                r = defs.get('range', 120)
                rang_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                col = (60,200,100,40) if can else (200,60,60,30)
                pygame.draw.circle(rang_surf, col, (r,r), r)
                surf.blit(rang_surf, (int(gx*TILE_SIZE + TILE_SIZE//2 - r), int(gy*TILE_SIZE + TILE_SIZE//2 - r)))
    def can_place_preview(self,gx,gy):
        if gx<0 or gx>=GRID_W or gy<0 or gy>=GRID_H: return False
        if (gx,gy) in [s for s in self.map.spawn_tiles] or (gx,gy)==self.map.goal_tile: return False
        if self.map.grid[gy][gx]==1: return False
        if self.map.tower_map[gy][gx]==1: return False
        self.map.set_tower(gx,gy,True)
        ok=True
        combined = self.map.get_combined_grid()
        for s in self.map.spawn_tiles:
            if astar_on_grid(combined, s, self.map.goal_tile) is None:
                ok=False; break
        self.map.set_tower(gx,gy,False)
        return ok
        return ok

def draw_text(surf, text, x, y, color=WHITE, bold=False):
    f = font_bold if bold else font
    img = f.render(str(text), True, color)
    surf.blit(img, (x,y))
def draw_small_text(surf, text, x, y, color=WHITE):
    img = small_font.render(str(text), True, color)
    surf.blit(img, (x,y))

def main():
    game = Game()
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
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
                    if my < MAP_H_PX:
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
# tower_defense_final_optimized_ui.py
# Versión optimizada + UI y mapa mejorado sin quitar funcionalidades.
# Ejecutar con pygame instalado.

import pygame, sys, math, heapq, random
from collections import deque

# -----------------------
# CONFIG (pantalla más grande + HUD mayor)
# -----------------------
TILE_SIZE = 40        # agrandado para más "presencia"
GRID_W = 25
GRID_H = 14
MAP_W_PX = TILE_SIZE * GRID_W
MAP_H_PX = TILE_SIZE * GRID_H

HUD_HEIGHT = 180
SCREEN_W = MAP_W_PX
SCREEN_H = MAP_H_PX + HUD_HEIGHT

FPS = 60

# --- balance: reduce starting money slightly, adjust costs to encourage planning
START_MONEY = 200
TOWER_COST = 80
ULTIMATE_COST = 450

PROJECTILE_SPEED = 12
ENEMY_REPATH_INTERVAL = 36

BASE_WAVE_COUNT = 4
WAVE_INCREMENT = 2
WAVE_BASE_INTERVAL = 26
WAVE_MIN_INTERVAL = 8

SHADOW_OFFSET = 6
PARTICLE_COUNT = 14
DAMAGE_POPUP_LIFE = 0.9

# Colors
WHITE = (255,255,255)
BLACK = (0,0,0)
BG_TOP = (20,28,52)
BG_BOTTOM = (8,12,28)
YELLOW = (255,215,80)
RED = (220,70,70)
GREEN = (80,220,110)
GOLD = (240,200,60)
UI_BG = (14,14,18)

pygame.init()
screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
pygame.display.set_caption("Tower Defense — UI & Map Mejorado (Optimizado)")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 18)
font_bold = pygame.font.SysFont("Arial", 20, bold=True)
small_font = pygame.font.SysFont("Arial", 14)

RAND = random.Random(12345)  # semilla para reproducibilidad visual

# centralizar stats de torretas para mantener consistencia y permitir preview
TOWER_DEFS = {
    'basic':   {'range':140,'rate':0.55,'damage':22,'hp':120},
    'slow':    {'range':120,'rate':0.9,'damage':10,'hp':110,'slow_amount':0.45,'slow_time':1.75},
    'splash':  {'range':130,'rate':1.15,'damage':16,'hp':130,'splash_radius':44},
    'rapid':   {'range':120,'rate':0.18,'damage':9,'hp':90},
    'multi':   {'range':150,'rate':1.0,'damage':12,'hp':130,'multi_count':3,'spread_deg':20},
    'pierce':  {'range':160,'rate':1.4,'damage':28,'hp':140,'pierce_count':3},
    'ultimate':{'range':220,'rate':4.5,'damage':160,'hp':420,'aoe_radius':100}
}

# -----------------------
# Pathfinding A*
# -----------------------
def heuristic(a,b): return abs(a[0]-b[0]) + abs(a[1]-b[1])
def neighbors(node, grid):
    x,y = node
    for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
        nx,ny = x+dx, y+dy
        if 0<=nx<GRID_W and 0<=ny<GRID_H:
            if not grid[ny][nx]:
                yield (nx,ny)

def astar_on_grid(grid, start, goal):
    if start==goal: return [start]
    open_set=[]
    heapq.heappush(open_set,(heuristic(start,goal), 0, start))
    came_from={}
    cost_so_far={start:0}
    while open_set:
        _, cost, current = heapq.heappop(open_set)
        if current==goal:
            path=[current]
            while current in came_from:
                current = came_from[current]; path.append(current)
            path.reverse(); return path
        for n in neighbors(current, grid):
            new_cost = cost_so_far[current] + 1
            if n not in cost_so_far or new_cost < cost_so_far[n]:
                cost_so_far[n] = new_cost
                priority = new_cost + heuristic(n,goal)
                heapq.heappush(open_set, (priority, new_cost, n))
                came_from[n] = current
    return None

# -----------------------
# Procedural sprites (cached)
# -----------------------
def make_tower_sprite(kind):
    # More detailed rounded pixel-art: draw on a larger small canvas and scale up
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
    # draw rounded blob with gradient-like rings (pixel style)
    for y in range(small_size):
        for x in range(small_size):
            d = math.hypot(x-cx, y-cy)
            if d <= 9.0:
                small.set_at((x,y), base)
            elif d <= 10.5:
                rim = tuple(max(0, c-30) for c in base)
                small.set_at((x,y), rim)
    # subtle highlight
    hl = tuple(min(255, c+30) for c in base)
    for ox,oy in ((-2,-2),(-1,-2),(-2,-1)):
        px = cx+ox; py = cy+oy
        if 0<=px<small_size and 0<=py<small_size: small.set_at((px,py), hl)
    # emblem: more detailed center marks
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
    # scale up to target size (56x56) using nearest to keep crispness
    s = pygame.transform.scale(small, (56,56))
    return s

def make_enemy_sprite(kind):
    # More detailed rounded enemies on a larger small canvas scaled to 44x44
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

# -----------------------
# Effects: particles, popups, shake (slim, __slots__ for speed)
# -----------------------
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
    def draw(self,surf):
        alpha = max(0, int(255*(1-self.age/self.life)))
        txt = small_font.render(self.text, True, self.color)
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

# -----------------------
# Projectile
# -----------------------
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
        # straight bullets use provided vx,vy and do single-hit collisions
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
            # fallback homing
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

# -----------------------
# Tower (destructible) — ahora dibujamos sprite + cañón rotatorio encima
# -----------------------
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
        # copy extras
        for k,v in defs.items():
            if k not in ('range','rate','damage','hp'):
                self.extra[k] = v
        self.max_hp = self.hp
        self.sprite = SPRITES.get('tower_'+kind)
        self.recoil = 0.0
    def update(self, dt, enemies, projectiles, game):
        self.cooldown -= dt
        # recoil decays over time
        if self.recoil > 0:
            self.recoil = max(0.0, self.recoil - dt * 3.5)
        # nearest in range (squared distance)
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
        # sprite base (non-rotating) + rotating barrel drawn on top
        surf.blit(self.sprite, (int(self.x - self.sprite.get_width()/2), int(self.y - self.sprite.get_height()/2)))
        # decorative rivets / bolts (static details)
        riv_offs = [(-14,-6),(14,-6),(-12,8),(12,8)]
        for ox,oy in riv_offs:
            pygame.draw.circle(surf, (30,30,36), (int(self.x+ox*0.6), int(self.y+oy*0.6)), 2)
        # draw rotating barrel distinct per kind, apply recoil offset
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
            # wide glowing barrel
            pygame.draw.line(surf, (255,230,120), (int(start_x), int(start_y)), (int(ex), int(ey)), 8)
            pygame.draw.circle(surf, (255,200,60), (int(ex), int(ey)), 6)
        else:
            barrel_len = 18
            ex,ey = barrel_end(barrel_len)
            pygame.draw.line(surf, (230,230,230), (int(start_x), int(start_y)), (int(ex), int(ey)), 4)
    # health bar
        w = 40; h = 7
        bx = int(self.x - w//2); by = int(self.y - TILE_SIZE//2 - 12)
        pygame.draw.rect(surf, (30,30,30), (bx,by,w,h))
        hp_w = int(w * max(0, self.hp)/max(1, self.max_hp))
        pygame.draw.rect(surf, (60,200,90), (bx,by,hp_w,h))
        if self.kind == 'ultimate':
            pygame.draw.circle(surf, (255,220,100), (int(self.x), int(self.y)), 28, 3)
        # (range drawing handled centrally in Game.draw where selection/hover is known)

# -----------------------
# Enemy (con comportamiento de atacar torres)
# -----------------------
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
            if self.repath_timer >= ENEMY_REPATH_INTERVAL:
                self.repath_timer = 0
            return
        # else follow path
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
        # heavier shadow for depth
        pygame.draw.ellipse(surf, (8,8,8,200), (self.x-20, self.y-10+SHADOW_OFFSET, 40, 14))
        # tint and outline: draw a faint colored halo behind sprite to emphasize type
        tint_col = Enemy.TYPE_PROPS.get(self.kind, {}).get('color', (180,180,180))
        tint = pygame.Surface((48,48), pygame.SRCALPHA)
        tc = (min(255,tint_col[0]+20), min(255,tint_col[1]+20), min(255,tint_col[2]+20), 60)
        pygame.draw.circle(tint, tc, (24,24), 20)
        surf.blit(tint, (int(self.x - 24), int(self.y - 24)), special_flags=pygame.BLEND_RGBA_ADD)
        # draw sprite (centered)
        sprite = SPRITES.get('enemy_'+self.kind)
        surf.blit(sprite, (int(self.x - sprite.get_width()/2), int(self.y - sprite.get_height()/2)))
        # subtle texture: a few darker pixels to suggest scale
        for i in range(2):
            rx = int(self.x + RAND.randint(-6,6)); ry = int(self.y + RAND.randint(-6,2))
            pygame.draw.circle(surf, (0,0,0,24), (rx,ry), 1)
        # hp bar (smoothed)
        self.display_hp += (self.hp - self.display_hp) * 0.12
        hp_w = (TILE_SIZE-8) * max(0, self.display_hp / max(1, self.max_hp))
        rect_back = pygame.Rect(self.x - (TILE_SIZE-8)/2, self.y - TILE_SIZE//2 - 10, TILE_SIZE-8, 6)
        pygame.draw.rect(surf, (20,20,20), rect_back)
        pygame.draw.rect(surf, (60,200,90), (rect_back.x, rect_back.y, hp_w, rect_back.h))

# -----------------------
# Map & pre-render base (sin líneas de rejilla) + decor
# -----------------------
class GameMap:
    def __init__(self):
        self.grid = [ [0 for _ in range(GRID_W)] for __ in range(GRID_H) ]
        # preset obstacles (unchanged)
        for i in range(4,7):
            for j in range(5,8):
                if 0<=i<GRID_W and 0<=j<GRID_H: self.grid[j][i] = 1
        for i in range(10,13):
            for j in range(2,5):
                if 0<=i<GRID_W and 0<=j<GRID_H: self.grid[j][i] = 1
        for i in range(8,11):
            for j in range(8,11):
                if 0<=i<GRID_W and 0<=j<GRID_H: self.grid[j][i] = 1
        self.spawn_tiles = [
            (0, GRID_H//2),
            (0, max(1, GRID_H//3)),
            (0, min(GRID_H-2, 2*GRID_H//3))
        ]
        self.goal_tile = (GRID_W-1, GRID_H//2)
        self.tower_map = [ [0 for _ in range(GRID_W)] for __ in range(GRID_H) ]
        # tile noise for decor
        self.tile_noise = [ [RAND.randint(-12,12) for _ in range(GRID_W)] for __ in range(GRID_H) ]
        # pre-render base map visual (tiles + obstacles + subtle stones)
        self.base_surf = pygame.Surface((MAP_W_PX, MAP_H_PX))
        self._render_base()
    def _render_base(self):
        s = self.base_surf
        s.fill((0,0,0))
        # vertical gradient on base (tile-level will blend)
        for y in range(s.get_height()):
            t = y / (s.get_height()-1)
            r = int(BG_TOP[0] * (1-t) + BG_BOTTOM[0]*t)
            g = int(BG_TOP[1] * (1-t) + BG_BOTTOM[1]*t)
            b = int(BG_TOP[2] * (1-t) + BG_BOTTOM[2]*t)
            pygame.draw.line(s, (r,g,b), (0,y), (s.get_width(), y))
        # draw tiles with color variation and subtle stones (no grid lines)
        for ty in range(GRID_H):
            for tx in range(GRID_W):
                base = 76 + self.tile_noise[ty][tx]
                color = (base+10, base+18, base+26)
                rect = pygame.Rect(tx*TILE_SIZE, ty*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(s, color, rect)
                if self.grid[ty][tx] == 1:
                    pygame.draw.rect(s, (96,96,96), rect.inflate(-10,-10))
                # procedural stones: few semi-transparent small dots
                stone_count = (abs(self.tile_noise[ty][tx]) % 4)
                for i in range(stone_count):
                    rx = tx*TILE_SIZE + RAND.randint(6, TILE_SIZE-6)
                    ry = ty*TILE_SIZE + RAND.randint(6, TILE_SIZE-12)
                    rr = RAND.randint(1,2)
                    pygame.draw.circle(s, (0,0,0,30), (rx, ry), rr)
    def set_tower(self, gx, gy, val):
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
    def draw(self, surf, tower_map_overlay=None, path_tiles=None):
        # blit pre-rendered base
        surf.blit(self.base_surf, (0,0))
        # highlight path tiles subtly (non-invasive)
        if path_tiles:
            for (tx,ty) in path_tiles:
                rect = pygame.Rect(tx*TILE_SIZE, ty*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                overlay.fill((255,255,255,20))
                surf.blit(overlay, (rect.x, rect.y))
        # draw tower cells overlay (no grid borders)
        if tower_map_overlay is not None:
            for y in range(GRID_H):
                for x in range(GRID_W):
                    if tower_map_overlay[y][x] == 1:
                        rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                        inner = rect.inflate(-10, -10)
                        pygame.draw.rect(surf, (28,88,140), inner)
        # draw spawn/goal markers
        for s in self.spawn_tiles:
            sx,sy = s
            r = pygame.Rect(sx*TILE_SIZE+8, sy*TILE_SIZE+8, TILE_SIZE-16, TILE_SIZE-16)
            pygame.draw.rect(surf, (26,180,60), r, border_radius=6)
        gx,gy = self.goal_tile
        r2 = pygame.Rect(gx*TILE_SIZE+8, gy*TILE_SIZE+8, TILE_SIZE-16, TILE_SIZE-16)
        pygame.draw.rect(surf, (200,40,40), r2, border_radius=6)

# -----------------------
# Game (con caché astar)
# -----------------------
class Game:
    def __init__(self):
        self.map = GameMap()
        self.towers = []
        self.enemies = []
        self.projectiles = []
        self.particles = []
        self.muzzle_flashes = []
        self.popups = []
        self.money = START_MONEY
        self.lives = 18
        self.wave = 0
        self.wave_in_progress = False
        self.spawn_queue = []
        self.selected_tower_kind = 'basic'
        # caches for pathfinding
        self._combined_grid = self.map.get_combined_grid()
        self._grid_version = 0
        self._astar_cache = {}
        # pre-render background gradient (for map area)
        self._background = pygame.Surface((MAP_W_PX, MAP_H_PX))
        for y in range(self._background.get_height()):
            t = y / (self._background.get_height()-1)
            r = int(BG_TOP[0]*(1-t) + BG_BOTTOM[0]*t)
            g = int(BG_TOP[1]*(1-t) + BG_BOTTOM[1]*t)
            b = int(BG_TOP[2]*(1-t) + BG_BOTTOM[2]*t)
            pygame.draw.line(self._background, (r,g,b), (0,y), (MAP_W_PX,y))
    def mark_grid_dirty(self):
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
        # reduce interval gradually but keep spacing for playability
        interval = max(WAVE_BASE_INTERVAL - (self.wave-1)*1, WAVE_MIN_INTERVAL)
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
            speed = 0.85 + RAND.random()*0.5 + (self.wave-1)*0.02
            hp = int(props['hp_base'] + int((self.wave-1)*8) + RAND.randint(-4, 10))
            reward = max(1, props['reward'] + (self.wave-1)//2)
            self.spawn_queue.append({'frames':spawn_frames, 'spec':{'kind':kind,'speed':speed,'hp':hp,'reward':reward}})
        self.spawn_queue.sort(key=lambda s: s['frames'])
    def spawn_enemy(self,spec):
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
        # spawn queue
        if self.wave_in_progress and self.spawn_queue:
            for item in self.spawn_queue: item['frames'] -= 1
            while self.spawn_queue and self.spawn_queue[0]['frames'] <= 0:
                item = self.spawn_queue.pop(0)
                self.spawn_enemy(item['spec'])
        if self.wave_in_progress and not self.spawn_queue and not any(e.alive for e in self.enemies):
            self.wave_in_progress = False
        # towers
        for t in list(self.towers):
            t.update(dt, self.enemies, self.projectiles, self)
        # projectiles: update and collect survivors
        new_projectiles = []
        for p in self.projectiles:
            p.update(self.enemies)
            if p.alive:
                new_projectiles.append(p)
            else:
                if p.kind == 'splash':
                    tx,ty = p.x,p.y
                    radius = getattr(p.owner_tower,'extra',{}).get('splash_radius', getattr(p.owner_tower,'extra',{}).get('aoe_radius', 44))
                    r2 = radius*radius
                    for e in self.enemies:
                        if not e.alive: continue
                        dx = e.x - tx; dy = e.y - ty
                        if dx*dx + dy*dy <= r2:
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
        # update muzzle flashes
        for mf in list(self.muzzle_flashes):
            mf.update(dt)
            if mf.age >= mf.life:
                try: self.muzzle_flashes.remove(mf)
                except ValueError: pass
        # enemies update
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
        # towers destroyed -> free cells
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
        # particles & popups update
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
        # (muzzle flashes already pruned above)
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
        self.mark_grid_dirty()
        return True
    def draw(self, surf):
        # background + base map
        surf.blit(self._background, (0,0))
        # compute a "main" path highlight from first spawn to goal for visuals only
        path_tiles = self.tile_path_from_to(self.map.spawn_tiles[0], self.map.goal_tile)
        self.map.draw(surf, tower_map_overlay=self.map.tower_map, path_tiles=path_tiles)
        # draw towers
        for t in self.towers: t.draw(surf)
        # draw enemies (painter order)
        enemies_sorted = sorted(self.enemies, key=lambda en: en.y) if len(self.enemies) > 16 else self.enemies
        for e in enemies_sorted: e.draw(surf)
        # projectiles
        for p in self.projectiles: p.draw(surf)
        # particles & popups
        for part in self.particles: part.draw(surf)
        # muzzle flashes
        for mf in self.muzzle_flashes: mf.draw(surf)
        for pop in self.popups: pop.draw(surf)
        # HUD area (improved layout)
        hud_rect = pygame.Rect(0, MAP_H_PX, SCREEN_W, HUD_HEIGHT)
        pygame.draw.rect(surf, UI_BG, hud_rect)
        pygame.draw.line(surf, (40,40,60), (0, MAP_H_PX), (SCREEN_W, MAP_H_PX), 2)
        # Left column (money, lives, wave)
        left_x = 12
        draw_text(surf, "DINERO", left_x, MAP_H_PX + 10, color=GOLD)
        draw_text(surf, f"${self.money}", left_x, MAP_H_PX + 34, color=WHITE, bold=True)
        draw_text(surf, "VIDAS", left_x, MAP_H_PX + 72, color=RED)
        draw_text(surf, f"{self.lives}", left_x, MAP_H_PX + 96, color=WHITE, bold=True)
        draw_text(surf, "OLEADA", left_x, MAP_H_PX + 134, color=YELLOW)
        draw_text(surf, f"{self.wave}", left_x, MAP_H_PX + 158, color=WHITE, bold=True)
        # Center area (controls)
        center_x = SCREEN_W//2 - 200
        draw_text(surf, "CONTROLES", center_x, MAP_H_PX + 8, color=WHITE)
        draw_small_text(surf, "SPACE: iniciar oleada    1-7: seleccionar torreta    Clic: colocar", center_x, MAP_H_PX + 36, color=(200,200,200))
        draw_small_text(surf, f"Coste torre: ${TOWER_COST}    Ultimate: ${ULTIMATE_COST}", center_x, MAP_H_PX + 64, color=(200,200,200))
        # Right column: tower selection boxes with sprite and label
        right_x = SCREEN_W - 420
        box_w = 64; box_h = 72; gap = 14
        tower_kinds = [('1','basic'),('2','slow'),('3','splash'),('4','rapid'),('5','multi'),('6','pierce'),('7','ultimate')]
        # draw label
        draw_text(surf, "TORRETAS", right_x, MAP_H_PX + 8, color=WHITE)
        # draw boxes in two rows (wrap)
        for idx, (key, kind) in enumerate(tower_kinds):
            col = idx % 4
            row = idx // 4
            bx = right_x + col*(box_w + gap)
            by = MAP_H_PX + 36 + row*(box_h + 8)
            # highlight if selected
            sel = (self.selected_tower_kind == kind)
            box_rect = pygame.Rect(bx, by, box_w, box_h)
            pygame.draw.rect(surf, (40,40,50) if not sel else (60,90,140), box_rect, border_radius=6)
            # sprite scaled down to fit
            spr = SPRITES.get('tower_'+kind)
            if spr:
                spr_s = pygame.transform.smoothscale(spr, (48,48))
                surf.blit(spr_s, (bx + (box_w - spr_s.get_width())//2, by + 6))
            # label
            lbl = f"{key}"
            draw_small_text(surf, lbl, bx + 4, by + box_h - 18, color=WHITE)
            # show small stat hint (rate or special)
            if kind == 'rapid':
                draw_small_text(surf, "rápida", bx + 18, by + box_h - 18, color=(180,220,240))
            elif kind == 'multi':
                draw_small_text(surf, "spread", bx + 18, by + box_h - 18, color=(220,180,120))
            elif kind == 'pierce':
                draw_small_text(surf, "atraviesa", bx + 18, by + box_h - 18, color=(255,180,180))
            elif kind == 'ultimate':
                draw_small_text(surf, "ultimate", bx + 18, by + box_h - 18, color=GOLD)
        # preview placement highlight (semi-transparent)
        mx,my = pygame.mouse.get_pos()
        gx = mx // TILE_SIZE; gy = my // TILE_SIZE
        if my < MAP_H_PX:
            rect = pygame.Rect(gx*TILE_SIZE+6, gy*TILE_SIZE+6, TILE_SIZE-12, TILE_SIZE-12)
            can = self.can_place_preview(gx,gy)
            c = (40,200,100,110) if can else (200,60,60,110)
            overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
            overlay.fill(c)
            surf.blit(overlay, (rect.x, rect.y))
            # draw selected tower range preview
            kind = self.selected_tower_kind
            defs = TOWER_DEFS.get(kind)
            if defs:
                r = defs.get('range', 120)
                rang_surf = pygame.Surface((r*2, r*2), pygame.SRCALPHA)
                col = (60,200,100,40) if can else (200,60,60,30)
                pygame.draw.circle(rang_surf, col, (r,r), r)
                surf.blit(rang_surf, (int(gx*TILE_SIZE + TILE_SIZE//2 - r), int(gy*TILE_SIZE + TILE_SIZE//2 - r)))
    def can_place_preview(self,gx,gy):
        if gx<0 or gx>=GRID_W or gy<0 or gy>=GRID_H: return False
        if (gx,gy) in [s for s in self.map.spawn_tiles] or (gx,gy)==self.map.goal_tile: return False
        if self.map.grid[gy][gx]==1: return False
        if self.map.tower_map[gy][gx]==1: return False
        # temporarily place and check reachability
        self.map.set_tower(gx,gy,True)
        ok=True
        combined = self.map.get_combined_grid()
        for s in self.map.spawn_tiles:
            if astar_on_grid(combined, s, self.map.goal_tile) is None:
                ok=False; break
        self.map.set_tower(gx,gy,False)
        return ok

# helper draw text with optional bold
def draw_text(surf, text, x, y, color=WHITE, bold=False):
    f = font_bold if bold else font
    img = f.render(str(text), True, color)
    surf.blit(img, (x,y))
def draw_small_text(surf, text, x, y, color=WHITE):
    img = small_font.render(str(text), True, color)
    surf.blit(img, (x,y))

# -----------------------
# Main loop
# -----------------------
def main():
    game = Game()
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
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
                    if my < MAP_H_PX:
                        gx = mx // TILE_SIZE; gy = my // TILE_SIZE
                        placed = game.place_tower(gx, gy, kind=game.selected_tower_kind)
                        if not placed:
                            game.popups.append(DamagePopup(mx, my-10, "No se puede colocar", RED))
        game.update(dt)
        off = SHAKE.offset()
        screen.fill(BLACK)
        # draw into a temp surf to apply shake offset
        temp = pygame.Surface((SCREEN_W, SCREEN_H))
        game.draw(temp)
        screen.blit(temp, (int(off[0]), int(off[1])))
        pygame.display.flip()
    pygame.quit(); sys.exit()

if __name__ == "__main__":
    main()
