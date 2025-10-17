import random
import math

# -----------------------
# CONFIG (pantalla más grande + HUD mayor)
# -----------------------
TILE_SIZE = 48        # agrandado para más "presencia"
GRID_W = 28
GRID_H = 11
MAP_W_PX = TILE_SIZE * GRID_W
MAP_H_PX = TILE_SIZE * GRID_H

# HUD height: choose a target fraction of the total window height (0.15-0.20 is recommended)
# We compute HUD_HEIGHT from MAP_H_PX so that HUD occupies approximately HUD_PCT of the
# final SCREEN_H. Formula: HUD = (pct / (1-pct)) * MAP_H_PX
# target HUD fraction of total window height (set between 0.30 and 0.40)
# target HUD fraction of total window height
HUD_PCT = 0.40  # legacy fraction (kept for reference)

# Option: force a fixed window height (do not grow SCREEN_H beyond this)
# Use SCREEN_H_FORCED to fix total window height; HUD_HEIGHT is derived so the map remains
# MAP_H_PX high and the HUD fills the remaining space. Change SCREEN_H_FORCED as needed.
SCREEN_H_FORCED = 800
HUD_HEIGHT = max(48, SCREEN_H_FORCED - MAP_H_PX)
SCREEN_W = MAP_W_PX
SCREEN_H = MAP_H_FORCED = SCREEN_H_FORCED

FPS = 60

# --- balance
START_MONEY = 500
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

RAND = random.Random(12345)

# centralizar stats de torretas
TOWER_DEFS = {
    'basic':   {'range':140,'rate':0.55,'damage':22,'hp':120},
    'slow':    {'range':120,'rate':0.9,'damage':10,'hp':110,'slow_amount':0.45,'slow_time':1.75},
    'splash':  {'range':130,'rate':1.15,'damage':16,'hp':130,'splash_radius':44},
    'rapid':   {'range':120,'rate':0.18,'damage':9,'hp':90},
    'multi':   {'range':150,'rate':1.0,'damage':12,'hp':130,'multi_count':3,'spread_deg':20},
    'pierce':  {'range':160,'rate':1.4,'damage':28,'hp':140,'pierce_count':3},
    'ultimate':{'range':220,'rate':4.5,'damage':160,'hp':420,'aoe_radius':100}
}
