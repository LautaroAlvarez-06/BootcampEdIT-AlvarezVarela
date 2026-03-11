"""
╔══════════════════════════════════════════╗
║   SNAKE GAME — Python + Pygame           ║
║   Instalar: pip install pygame           ║
║   Ejecutar: python3 snake_pygame.py      ║
╚══════════════════════════════════════════╝
Controles:
  Flechas / WASD  → Mover
  P               → Pausa
  R               → Reiniciar
  ESC             → Salir
"""

import pygame
import random
import sys
import os
import json

# ─── Configuración ────────────────────────────────────────────────────────────
COLS        = 24
ROWS        = 24
CELL        = 24
WIDTH       = COLS * CELL
HEIGHT      = ROWS * CELL
HUD_HEIGHT  = 70
WIN_W       = WIDTH
WIN_H       = HEIGHT + HUD_HEIGHT
FPS         = 60
TICK_START  = 140       # ms entre movimientos
TICK_MIN    = 60
TICK_STEP   = 10        # ms menos por nivel
POINTS_LVL  = 50
BEST_FILE   = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".snake_best.json")

# ─── Paleta de colores ────────────────────────────────────────────────────────
BG          = (2,   8,  16)
GRID_CLR    = (10,  26,  14)
HUD_BG      = (4,  15,  30)
HEAD_CLR    = (0,  255, 136)
TAIL_CLR    = (0,   80,  50)
EYE_CLR     = (0,  255, 200)
FOOD_CLR    = (255, 234,  0)
FOOD_RIM    = (255, 140,  0)
CYAN        = (0,  229, 255)
PINK        = (255,  0, 128)
WHITE       = (220, 255, 240)
DIM         = (30,  80,  40)
BLACK       = (0,    0,   0)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def lerp_color(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def load_best():
    try:
        with open(BEST_FILE) as f:
            return json.load(f).get("best", 0)
    except Exception:
        return 0


def save_best(val):
    try:
        with open(BEST_FILE, "w") as f:
            json.dump({"best": val}, f)
    except Exception:
        pass


def draw_rounded_rect(surface, color, rect, radius=5, border=0, border_color=None):
    pygame.draw.rect(surface, color, rect, border_radius=radius)
    if border and border_color:
        pygame.draw.rect(surface, border_color, rect, width=border, border_radius=radius)


# ─── Partículas ───────────────────────────────────────────────────────────────
class Particle:
    def __init__(self, x, y, color):
        angle  = random.uniform(0, 2 * 3.14159)
        speed  = random.uniform(1.5, 5.0)
        self.x = float(x)
        self.y = float(y)
        self.vx = speed * __import__("math").cos(angle)
        self.vy = speed * __import__("math").sin(angle)
        self.life    = 1.0
        self.decay   = random.uniform(0.025, 0.055)
        self.color   = color
        self.radius  = random.uniform(2, 5)

    def update(self):
        self.x    += self.vx
        self.y    += self.vy
        self.vy   += 0.12
        self.life -= self.decay

    def draw(self, surface):
        if self.life <= 0:
            return
        alpha = max(0, int(self.life * 255))
        r     = max(1, int(self.radius * self.life))
        color = (*self.color[:3], alpha)
        surf  = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, color, (r, r), r)
        surface.blit(surf, (int(self.x) - r, int(self.y) - r))


# ─── Lógica de la serpiente ───────────────────────────────────────────────────
class Snake:
    def __init__(self):
        mid = COLS // 2
        self.body      = [(mid, ROWS // 2), (mid - 1, ROWS // 2), (mid - 2, ROWS // 2)]
        self.direction = (1, 0)
        self.next_dir  = (1, 0)
        self.grow      = False

    def set_direction(self, dx, dy):
        if (dx, dy) != (-self.direction[0], -self.direction[1]):
            self.next_dir = (dx, dy)

    def step(self):
        self.direction = self.next_dir
        dx, dy = self.direction
        hx, hy = self.body[0]
        new_head = (hx + dx, hy + dy)
        self.body.insert(0, new_head)
        if not self.grow:
            self.body.pop()
        self.grow = False
        return new_head

    def head(self):
        return self.body[0]

    def collides_wall(self):
        x, y = self.body[0]
        return x < 0 or x >= COLS or y < 0 or y >= ROWS

    def collides_self(self):
        return self.body[0] in self.body[1:]


# ─── Juego principal ──────────────────────────────────────────────────────────
class Game:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("SNAKE // NEON GRID")
        self.screen  = pygame.display.set_mode((WIN_W, WIN_H))
        self.clock   = pygame.time.Clock()

        # Fuentes
        self.font_big    = pygame.font.SysFont("Courier New", 36, bold=True)
        self.font_med    = pygame.font.SysFont("Courier New", 18, bold=True)
        self.font_small  = pygame.font.SysFont("Courier New", 13)
        self.font_hud    = pygame.font.SysFont("Courier New", 22, bold=True)
        self.font_label  = pygame.font.SysFont("Courier New", 10)

        self.best        = load_best()
        self.particles   = []
        self.food_tick   = 0
        self.tick_accum  = 0
        self.state       = "start"   # start | playing | paused | gameover
        self.snake       = None
        self.food        = (0, 0)
        self.score       = 0
        self.level       = 1
        self.tick_speed  = TICK_START

        # Superficie de juego (separada del HUD)
        self.game_surf   = pygame.Surface((WIDTH, HEIGHT))

        # Grilla precalculada
        self.grid_surf   = pygame.Surface((WIDTH, HEIGHT))
        self._bake_grid()

    # ── Grid ──────────────────────────────────────────────────────────────────
    def _bake_grid(self):
        self.grid_surf.fill(BG)
        for x in range(0, WIDTH + 1, CELL):
            pygame.draw.line(self.grid_surf, GRID_CLR, (x, 0), (x, HEIGHT))
        for y in range(0, HEIGHT + 1, CELL):
            pygame.draw.line(self.grid_surf, GRID_CLR, (0, y), (WIDTH, y))

    # ── Iniciar partida ───────────────────────────────────────────────────────
    def new_game(self):
        self.snake       = Snake()
        self.score       = 0
        self.level       = 1
        self.tick_speed  = TICK_START
        self.tick_accum  = 0
        self.food_tick   = 0
        self.particles   = []
        self._place_food()
        self.state       = "playing"

    def _place_food(self):
        occupied = set(self.snake.body)
        while True:
            pos = (random.randint(0, COLS - 1), random.randint(0, ROWS - 1))
            if pos not in occupied:
                self.food = pos
                break

    # ── Ciclo principal ───────────────────────────────────────────────────────
    def run(self):
        while True:
            dt = self.clock.tick(FPS)
            self._handle_events()
            self._update(dt)
            self._draw()
            pygame.display.flip()

    # ── Eventos ───────────────────────────────────────────────────────────────
    def _handle_events(self):
        dir_map = {
            pygame.K_UP:    (0, -1), pygame.K_w: (0, -1),
            pygame.K_DOWN:  (0,  1), pygame.K_s: (0,  1),
            pygame.K_LEFT:  (-1, 0), pygame.K_a: (-1, 0),
            pygame.K_RIGHT: (1,  0), pygame.K_d: (1,  0),
        }
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

                if self.state == "start":
                    if event.key in (pygame.K_RETURN, pygame.K_SPACE):
                        self.new_game()

                elif self.state == "playing":
                    if event.key in dir_map:
                        self.snake.set_direction(*dir_map[event.key])
                    elif event.key == pygame.K_p:
                        self.state = "paused"
                    elif event.key == pygame.K_r:
                        self.new_game()

                elif self.state == "paused":
                    if event.key in (pygame.K_p, pygame.K_RETURN):
                        self.state = "playing"
                    elif event.key == pygame.K_r:
                        self.new_game()

                elif self.state == "gameover":
                    if event.key in (pygame.K_r, pygame.K_RETURN, pygame.K_SPACE):
                        self.new_game()

    # ── Actualización ─────────────────────────────────────────────────────────
    def _update(self, dt):
        # Partículas siempre actualizan
        for p in self.particles:
            p.update()
        self.particles = [p for p in self.particles if p.life > 0]

        if self.state != "playing":
            return

        self.food_tick += dt
        self.tick_accum += dt

        if self.tick_accum < self.tick_speed:
            return
        self.tick_accum = 0

        self.snake.step()

        if self.snake.collides_wall() or self.snake.collides_self():
            self._on_death()
            return

        if self.snake.head() == self.food:
            self.snake.grow = True
            self.score += self.level * 10
            if self.score > self.best:
                self.best = self.score
                save_best(self.best)
            # Partículas al comer
            fx = self.food[0] * CELL + CELL // 2
            fy = self.food[1] * CELL + CELL // 2
            for _ in range(16):
                self.particles.append(Particle(fx, fy + HUD_HEIGHT, FOOD_CLR))
            # Subir nivel
            new_level = self.score // POINTS_LVL + 1
            if new_level != self.level:
                self.level = new_level
                self.tick_speed = max(TICK_MIN, TICK_START - (self.level - 1) * TICK_STEP)
            self._place_food()

    def _on_death(self):
        hx = self.snake.head()[0] * CELL + CELL // 2
        hy = self.snake.head()[1] * CELL + CELL // 2
        for _ in range(30):
            self.particles.append(Particle(hx, hy + HUD_HEIGHT, PINK))
        self.state = "gameover"

    # ── Dibujo ────────────────────────────────────────────────────────────────
    def _draw(self):
        self.screen.fill(BG)
        self._draw_hud()
        self._draw_game()
        self._draw_particles()
        if self.state == "start":
            self._draw_overlay("NEON GRID",
                               "Come los nodos amarillos.",
                               "Evita bordes y tu propia cola.",
                               "[ENTER] o [ESPACIO] para iniciar")
        elif self.state == "paused":
            self._draw_overlay("— PAUSA —",
                               f"Puntaje: {self.score}   Nivel: {self.level}",
                               "",
                               "[P] o [ENTER] para continuar  |  [R] reiniciar")
        elif self.state == "gameover":
            self._draw_overlay("GAME OVER",
                               f"Puntaje: {self.score}   Nivel: {self.level}",
                               f"Récord: {self.best}",
                               "[R] o [ENTER] para reintentar")

    # ── HUD ───────────────────────────────────────────────────────────────────
    def _draw_hud(self):
        pygame.draw.rect(self.screen, HUD_BG, (0, 0, WIN_W, HUD_HEIGHT))
        pygame.draw.line(self.screen, HEAD_CLR, (0, HUD_HEIGHT - 1), (WIN_W, HUD_HEIGHT - 1))

        col_w = WIN_W // 3
        panels = [
            ("SCORE", str(self.score).zfill(4)),
            ("LEVEL", str(self.level).zfill(2)),
            ("BEST",  str(self.best).zfill(4)),
        ]
        for i, (label, value) in enumerate(panels):
            cx = col_w * i + col_w // 2
            lbl_surf = self.font_label.render(label, True, CYAN)
            val_surf = self.font_hud.render(value, True, CYAN)
            self.screen.blit(lbl_surf, (cx - lbl_surf.get_width() // 2, 10))
            self.screen.blit(val_surf, (cx - val_surf.get_width() // 2, 24))
            if i > 0:
                pygame.draw.line(self.screen, DIM,
                                 (col_w * i, 8), (col_w * i, HUD_HEIGHT - 12))

        # Barra de progreso de nivel
        progress = (self.score % POINTS_LVL) / POINTS_LVL if self.state != "start" else 0
        bar_y  = HUD_HEIGHT - 8
        bar_h  = 4
        pygame.draw.rect(self.screen, DIM, (8, bar_y, WIN_W - 16, bar_h), border_radius=2)
        if progress > 0:
            pygame.draw.rect(self.screen, HEAD_CLR,
                             (8, bar_y, int((WIN_W - 16) * progress), bar_h),
                             border_radius=2)

    # ── Zona de juego ─────────────────────────────────────────────────────────
    def _draw_game(self):
        self.game_surf.blit(self.grid_surf, (0, 0))

        if self.state in ("playing", "paused", "gameover") and self.snake:
            self._draw_food_surf()
            self._draw_snake_surf()

        self.screen.blit(self.game_surf, (0, HUD_HEIGHT))

    def _draw_food_surf(self):
        fx, fy = self.food
        cx = fx * CELL + CELL // 2
        cy = fy * CELL + CELL // 2
        pulse = abs((self.food_tick % 600) / 300 - 1)   # 0→1→0 cada 600ms
        r = int(CELL * 0.30 + pulse * 4)

        # Anillos de brillo
        for i in range(3, 0, -1):
            ring_r = r + i * 4
            alpha  = int(40 * pulse * i / 3)
            ring_s = pygame.Surface((ring_r * 2, ring_r * 2), pygame.SRCALPHA)
            pygame.draw.circle(ring_s, (*FOOD_CLR, alpha), (ring_r, ring_r), ring_r, 1)
            self.game_surf.blit(ring_s, (cx - ring_r, cy - ring_r))

        # Núcleo
        pygame.draw.circle(self.game_surf, FOOD_RIM, (cx, cy), r + 2)
        pygame.draw.circle(self.game_surf, FOOD_CLR, (cx, cy), r)
        # Destello central
        pygame.draw.circle(self.game_surf, WHITE, (cx - r // 3, cy - r // 3), max(1, r // 4))

        # Cruz de mira
        cr = r + 6
        pygame.draw.line(self.game_surf, FOOD_CLR, (cx - cr, cy), (cx + cr, cy), 1)
        pygame.draw.line(self.game_surf, FOOD_CLR, (cx, cy - cr), (cx, cy + cr), 1)

    def _draw_snake_surf(self):
        body = self.snake.body
        n    = len(body)
        is_dead = self.state == "gameover"

        for i, (x, y) in enumerate(body):
            t     = i / max(n - 1, 1)
            color = PINK if is_dead else lerp_color(HEAD_CLR, TAIL_CLR, t)
            rect  = pygame.Rect(x * CELL + 2, y * CELL + 2, CELL - 4, CELL - 4)
            border_color = (255, 80, 140) if is_dead else (lerp_color(HEAD_CLR, DIM, t))
            draw_rounded_rect(self.game_surf, color, rect, radius=4,
                              border=1 if i == 0 else 0,
                              border_color=border_color)

        # Ojos en la cabeza
        if not is_dead:
            dx, dy = self.snake.direction
            hx, hy = body[0]
            cx = hx * CELL + CELL // 2
            cy = hy * CELL + CELL // 2
            off = CELL // 4

            if   dx ==  1: eyes = [(cx + off, cy - off), (cx + off, cy + off)]
            elif dx == -1: eyes = [(cx - off, cy - off), (cx - off, cy + off)]
            elif dy == -1: eyes = [(cx - off, cy - off), (cx + off, cy - off)]
            else:          eyes = [(cx - off, cy + off), (cx + off, cy + off)]

            for ex, ey in eyes:
                pygame.draw.circle(self.game_surf, EYE_CLR, (ex, ey), 2)

    # ── Partículas ────────────────────────────────────────────────────────────
    def _draw_particles(self):
        for p in self.particles:
            p.draw(self.screen)

    # ── Overlay ───────────────────────────────────────────────────────────────
    def _draw_overlay(self, title, line1, line2, action):
        # Fondo semitransparente
        overlay = pygame.Surface((WIN_W, WIN_H), pygame.SRCALPHA)
        overlay.fill((2, 8, 16, 200))
        self.screen.blit(overlay, (0, 0))

        # Panel
        panel_w, panel_h = 420, 200
        px = (WIN_W - panel_w) // 2
        py = (WIN_H - panel_h) // 2
        panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel.fill((4, 20, 40, 230))
        self.screen.blit(panel, (px, py))
        pygame.draw.rect(self.screen, HEAD_CLR,
                         (px, py, panel_w, panel_h), width=2, border_radius=4)

        cy = py + 30
        # Título
        t = self.font_big.render(title, True, PINK)
        self.screen.blit(t, (WIN_W // 2 - t.get_width() // 2, cy))
        cy += 50

        # Líneas de info
        for line in (line1, line2):
            if line:
                s = self.font_med.render(line, True, WHITE)
                self.screen.blit(s, (WIN_W // 2 - s.get_width() // 2, cy))
                cy += 26

        # Acción
        a = self.font_small.render(action, True, HEAD_CLR)
        self.screen.blit(a, (WIN_W // 2 - a.get_width() // 2, py + panel_h - 30))


# ─── Entrada ──────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    game = Game()
    game.run()