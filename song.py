import tkinter as tk
import time
import math
import random


LYRICS = [
    (0,  "I want one ticket out of your heavy gaze"),
    (4,  "I want one ticket off of your carousel"),
    (9,  "But you should know that I die slow"),
    (13, "Running through the halls of your haunted home"),
    (18, "And the toughest part is that we both know"),
    (22, "What happened to you"),
    (24, "Why you′re out on your own"),
    (26, "Merry Christmas, please don't call"),
    (31, "Merry Christmas, I′m not yours at all"),
    (36, "Merry Christmas, please don't call me"),
    (41, "Please don′t call me"),
    (45, "Please don't call me"),
    (49, "Please don't call me"),
]

AUTO_GAP = 4


def load_lyrics(path="lyrics.txt"):
    """Baca lyrics.txt di folder yang sama.
    Format per baris (pilih salah satu):
        12|teks lirik     -> muncul di detik ke-12
        teks lirik        -> waktu otomatis tiap AUTO_GAP detik
    Baris kosong dan baris seperti [Chorus] dilewati.
    """
    try:
        with open(path, encoding="utf-8") as f:
            lines = [l.strip() for l in f]
    except OSError:
        return None
    result, auto_t = [], 0.0
    for line in lines:
        if not line or (line.startswith("[") and line.endswith("]")):
            continue
        head, sep, rest = line.partition("|")
        if sep and head.strip().replace(".", "", 1).isdigit():
            t = float(head)
            result.append((t, rest.strip()))
            auto_t = t + AUTO_GAP
        else:
            result.append((auto_t, line))
            auto_t += AUTO_GAP
    return result or None


LYRICS = load_lyrics() or LYRICS

BOX_W, BOX_H = 320, 260
FONT = ("Georgia", 20, "bold")
RISE_SPEED = 67            
BOTTOM_SPAWN_OFFSET = 150  
TYPE_SPEED = 14
SNOW_COUNT = 170
FPS = 60

BG_COLOR = "#0A0000"


THEMES = [
    {"bg": "#141414", "border": "#B82E2E", "text": "#F5F0E6", "dot": "#D42F2F"},  # dark glass
    {"bg": "#C41E1E", "border": "#FF6B6B", "text": "#FFF3EE", "dot": "#FF8A8A"},  # red
    {"bg": "#F1E7E2", "border": "#E05252", "text": "#A81818", "dot": "#D42F2F"},  # light
]


def rounded_rect(cv, x1, y1, x2, y2, r, **kw):
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r,
           x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2,
           x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class Card:
    def __init__(self, text, x, y, theme, t0, lane=0):
        self.lane = lane
        self.text = f"\u201c{text}\u201d"
        self.x, self.y = x, y
        self.theme = theme
        self.t0 = t0
        self.items = []

    def shown_text(self, now):
        n = int((now - self.t0) * TYPE_SPEED)
        return self.text[:max(1, n)]

    def draw(self, cv, now):
        for i in self.items:
            cv.delete(i)
        self.items.clear()
        th, x, y = self.theme, self.x, self.y
        self.items.append(rounded_rect(cv, x, y, x + BOX_W, y + BOX_H, 22,
                                       fill=th["bg"], outline=th["border"], width=3))
        # "kamera" kecil di tengah atas kartu
        self.items.append(cv.create_oval(x + BOX_W / 2 - 4, y + 9, x + BOX_W / 2 + 4, y + 17,
                                         fill=th["border"], outline=""))
        # kotak kecil di pojok kiri bawah
        self.items.append(cv.create_rectangle(x + 14, y + BOX_H - 30, x + 30, y + BOX_H - 14,
                                              fill=th["dot"], outline=""))
        self.items.append(cv.create_text(x + BOX_W / 2, y + BOX_H / 2 - 6,
                                         text=self.shown_text(now), fill=th["text"],
                                         font=FONT, width=BOX_W - 60, justify="center"))


class App:
    def __init__(self, root):
        self.root = root
        root.title("song.py")
        root.configure(bg=BG_COLOR)
        root.geometry("1280x720")
        self.cv = tk.Canvas(root, bg=BG_COLOR, highlightthickness=0)
        self.cv.pack(fill="both", expand=True)
        root.bind("<Escape>", lambda e: root.destroy())
        root.bind("<F11>", lambda e: root.attributes("-fullscreen",
                                                     not root.attributes("-fullscreen")))
        self.W, self.H = 1280, 720
        self.cv.bind("<Configure>", self.on_resize)

        self.start = time.time()
        self.next_idx = 0
        self.cards = []
        self.pending = []
        self.theme_i = 0
        self.last = self.start

        self.snow = [[random.random(), random.random(),
                      random.uniform(1, 2.6), random.uniform(20, 70),
                      random.uniform(0, 6.28)] for _ in range(SNOW_COUNT)]
        self.notes = []
        self.play_audio()
        self.tick()

    # Opsional: taruh song.mp3 di folder yang sama (butuh: pip install pygame)
    def play_audio(self):
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load("song.mp3")
            pygame.mixer.music.play()
        except Exception:
            pass

    def on_resize(self, e):
        self.W, self.H = e.width, e.height

    def pick_lane(self):
        """Cari jalur (kolom) yang kosong di bawah layar. None kalau semua masih penuh."""
        gap = 20
        n = max(1, (self.W - gap) // (BOX_W + gap))
        spawn_y = self.H + BOTTOM_SPAWN_OFFSET
        lanes = list(range(n))
        random.shuffle(lanes)
        for l in lanes:
            if all(not (c.lane == l and c.y + BOX_H + gap > spawn_y) for c in self.cards):
                total = n * BOX_W + (n - 1) * gap
                left = (self.W - total) / 2
                return l, left + l * (BOX_W + gap)
        return None

    def spawn_card(self, text, now):
        lane = self.pick_lane()
        if lane is None:
            return False  # semua jalur penuh, coba lagi frame berikutnya
        l, x = lane
        y = self.H + BOTTOM_SPAWN_OFFSET
        theme = THEMES[self.theme_i % len(THEMES)]
        self.theme_i += 1
        self.cards.append(Card(text, x, y, theme, now, l))
        for _ in range(2):
            self.notes.append([x + random.randint(0, BOX_W), y, random.uniform(30, 60),
                               random.choice(["\u266a", "\u266b"])])
        return True

    def tick(self):
        now = time.time()
        dt = now - self.last
        self.last = now
        t = now - self.start
        cv = self.cv
        cv.delete("f")  # frame objects (salju, nada, scene)

        # lirik sesuai waktu
        while self.next_idx < len(LYRICS) and t >= LYRICS[self.next_idx][0]:
            self.pending.append(LYRICS[self.next_idx][1])
            self.next_idx += 1
        if self.pending and self.spawn_card(self.pending[0], now):
            self.pending.pop(0)

        # salju
        for s in self.snow:
            s[1] += s[3] * dt / self.H
            s[0] += math.sin(now + s[4]) * 0.0004
            if s[1] > 1:
                s[1], s[0] = 0, random.random()
            px, py, r = s[0] * self.W, s[1] * self.H, s[2]
            cv.create_oval(px - r, py - r, px + r, py + r, fill="white", outline="", tags="f")

        # nada musik merah
        for n in self.notes[:]:
            n[1] -= n[2] * dt
            n[0] += math.sin(now * 2 + n[1] / 40) * 0.5
            if n[1] < -30:
                self.notes.remove(n)
                continue
            cv.create_text(n[0], n[1], text=n[3], fill="#C0392B",
                           font=("Segoe UI Symbol", 16), tags="f")

        # kartu naik ke atas
        for c in self.cards[:]:
            c.y -= RISE_SPEED * dt
            if c.y < -BOX_H - 20:
                for i in c.items:
                    cv.delete(i)
                self.cards.remove(c)
                continue
            c.draw(cv, now)

        self.root.after(int(1000 / FPS), self.tick)


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()