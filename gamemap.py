import heapq, math
from config import GRID_W, GRID_H, TILE_SIZE, MAP_W_PX, MAP_H_PX, RAND

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

class GameMap:
    def __init__(self):
        self.grid = [ [0 for _ in range(GRID_W)] for __ in range(GRID_H) ]
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
        self.tile_noise = [ [RAND.randint(-12,12) for _ in range(GRID_W)] for __ in range(GRID_H) ]
        self.base_surf = None
        self._render_base()
    def _render_base(self):
        import pygame
        from config import MAP_W_PX, MAP_H_PX, BG_TOP, BG_BOTTOM, TILE_SIZE
        s = pygame.Surface((MAP_W_PX, MAP_H_PX))
        s.fill((0,0,0))
        for y in range(s.get_height()):
            t = y / (s.get_height()-1)
            r = int(BG_TOP[0] * (1-t) + BG_BOTTOM[0]*t)
            g = int(BG_TOP[1] * (1-t) + BG_BOTTOM[1]*t)
            b = int(BG_TOP[2] * (1-t) + BG_BOTTOM[2]*t)
            pygame.draw.line(s, (r,g,b), (0,y), (s.get_width(), y))
        for ty in range(GRID_H):
            for tx in range(GRID_W):
                base = 76 + self.tile_noise[ty][tx]
                color = (base+10, base+18, base+26)
                rect = pygame.Rect(tx*TILE_SIZE, ty*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                pygame.draw.rect(s, color, rect)
                if self.grid[ty][tx] == 1:
                    pygame.draw.rect(s, (96,96,96), rect.inflate(-10,-10))
                stone_count = (abs(self.tile_noise[ty][tx]) % 4)
                for i in range(stone_count):
                    rx = tx*TILE_SIZE + RAND.randint(6, TILE_SIZE-6)
                    ry = ty*TILE_SIZE + RAND.randint(6, TILE_SIZE-12)
                    rr = RAND.randint(1,2)
                    pygame.draw.circle(s, (0,0,0,30), (rx, ry), rr)
        self.base_surf = s
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
        import pygame
        from config import MAP_W_PX, MAP_H_PX, TILE_SIZE, GRID_H, GRID_W
        surf.blit(self.base_surf, (0,0))
        if path_tiles:
            for (tx,ty) in path_tiles:
                rect = pygame.Rect(tx*TILE_SIZE, ty*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
                overlay.fill((255,255,255,20))
                surf.blit(overlay, (rect.x, rect.y))
        if tower_map_overlay is not None:
            for y in range(GRID_H):
                for x in range(GRID_W):
                    if tower_map_overlay[y][x] == 1:
                        rect = pygame.Rect(x*TILE_SIZE, y*TILE_SIZE, TILE_SIZE, TILE_SIZE)
                        inner = rect.inflate(-10, -10)
                        pygame.draw.rect(surf, (28,88,140), inner)
        for s in self.spawn_tiles:
            sx,sy = s
            r = pygame.Rect(sx*TILE_SIZE+8, sy*TILE_SIZE+8, TILE_SIZE-16, TILE_SIZE-16)
            pygame.draw.rect(surf, (26,180,60), r, border_radius=6)
        gx,gy = self.goal_tile
        r2 = pygame.Rect(gx*TILE_SIZE+8, gy*TILE_SIZE+8, TILE_SIZE-16, TILE_SIZE-16)
        pygame.draw.rect(surf, (200,40,40), r2, border_radius=6)
