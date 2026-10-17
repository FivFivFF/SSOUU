import os
import sys
import math
import random
import pygame
import numpy as np
import librosa

# Глобальные переменные состояния
game_objects = []
results = []
hit_effects = []
particles = []
bg_particles = []
click_ripples = []
flash_intensity = 0
combo = 0
score = 0
is_holding_slider = None
combo_scale_timer = 0


def update_object_colors():
    """Делает самый старый (первый по порядку появления) кружок красным, а остальные — цветастыми"""
    if not game_objects:
        return

    trail_colors = [
        (0, 220, 255),  # Неоновый циан
        (180, 50, 255),  # Фиолетовый
        (50, 255, 150)  # Сочный зеленый
    ]

    for idx, obj in enumerate(game_objects):
        if idx == 0:
            obj.color = (255, 60, 60)  # Самый старый кружок (цель для удара) всегда красный
        else:
            obj.color = trail_colors[(idx - 1) % len(trail_colors)]


class Song:
    def __init__(self, title, file_path):
        self.title = title
        self.file_path = file_path
        self.duration_ms = 0
        self.beatmap = []
        self.approach_time = 850  # Ускоренное приближение (быстрые шарики)
        self.tempo = 120
        self.y = None
        self.sr = 22050
        self.analyze_audio()

    def analyze_audio(self):
        print(f"Аналіз збалансованого ритму та слайдерів для: {self.title}... Зачекайте.")
        try:
            self.y, self.sr = librosa.load(self.file_path, sr=None)
            self.duration_ms = int(librosa.get_duration(y=self.y, sr=self.sr) * 1000)

            y_harmonic, y_percussive = librosa.effects.hpss(self.y)

            tempo_arr, _ = librosa.beat.beat_track(y=self.y, sr=self.sr)
            if hasattr(tempo_arr, "__len__"):
                self.tempo = float(tempo_arr[0]) if len(tempo_arr) > 0 else 120.0
            else:
                self.tempo = float(tempo_arr)

            if self.tempo > 0:
                # Уменьшаем время появления для более высокой скорости и динамики
                self.approach_time = max(650, int(38000 / self.tempo) + 250)

            o_env = librosa.onset.onset_strength(y=y_percussive, sr=self.sr)
            onset_frames = librosa.onset.onset_detect(onset_envelope=o_env, sr=self.sr, backtrack=True, units='frames',
                                                      delta=0.015)
            onset_times = librosa.frames_to_time(onset_frames, sr=self.sr)

            raw_times = [int(t * 1000) for t in onset_times if t * 1000 >= 1000]

            filtered_beats = []
            for t in raw_times:
                frame_idx = librosa.time_to_frames(t / 1000.0, sr=self.sr)
                strength = o_env[frame_idx] if frame_idx < len(o_env) else 0.0

                # Снижаем порог силы, чтобы ловить больше нот (увеличиваем количество шариков)
                if strength < 0.20:
                    continue

                # Уменьшаем минимальный интервал между нотами для высокой плотности шариков
                min_gap = 200 if self.tempo > 130 else 280
                if not filtered_beats or t - filtered_beats[-1] >= min_gap:
                    filtered_beats.append(t)

            self.beatmap = []
            i = 0
            while i < len(filtered_beats):
                hit_time = filtered_beats[i]
                sound = self.extract_hit_sound(y_harmonic, self.sr, hit_time)

                if i + 1 < len(filtered_beats) and random.random() < 0.05:
                    start_t = filtered_beats[i]
                    next_t = filtered_beats[i + 1]
                    duration = next_t - start_t
                    if 200 <= duration <= 600:
                        self.beatmap.append(('slider', (start_t, duration), sound))
                        i += 2
                        continue

                self.beatmap.append(('circle', hit_time, sound))
                i += 1

            print(f"Готово! Згенеровано об'єктів: {len(self.beatmap)}.")
        except Exception as e:
            print(f"Помилка аналізу файлу ({e}). Використовуємо базовий темп.")
            self.duration_ms = 180000
            self.approach_time = 850
            self.tempo = 120
            default_sound = self.generate_fallback_sound()
            self.beatmap = [('circle', 1000 + i * 250, default_sound) for i in range(300)]

    def extract_hit_sound(self, y_harmonic, sr, time_ms):
        """Вырезает короткий отрывок (0.1 сек) с тихой громкостью"""
        try:
            sample_start = int((time_ms / 1000.0) * sr)
            sample_duration = int(0.1 * sr)  # 0.1 секунды отрывка
            sample_end = min(sample_start + sample_duration, len(y_harmonic))

            snippet = y_harmonic[sample_start:sample_end]
            if len(snippet) < sample_duration:
                snippet = np.pad(snippet, (0, sample_duration - len(snippet)))

            fade_len = int(sr * 0.01)
            if len(snippet) > fade_len * 2:
                snippet[:fade_len] *= np.linspace(0, 1, fade_len)
                snippet[-fade_len:] *= np.linspace(1, 0, fade_len)

            audio = (np.tanh(snippet * 1.0) * 16000).astype(np.int16)
            stereo = np.column_stack((audio, audio))
            sound = pygame.mixer.Sound(buffer=stereo.tobytes())
            sound.set_volume(0.2)
            return sound
        except Exception:
            return self.generate_fallback_sound()

    def generate_fallback_sound(self):
        sr = 22050
        duration = 0.1
        t = np.linspace(0, duration, int(sr * duration), endpoint=False)
        freq = 140 * np.exp(-t * 20) + 35
        wave = np.sin(2 * np.pi * freq * t) + 0.4 * np.sin(2 * np.pi * (freq * 2) * t)
        audio = (np.tanh(wave * 1.0) * 16000).astype(np.int16)
        stereo = np.column_stack((audio, audio))
        sound = pygame.mixer.Sound(buffer=stereo.tobytes())
        sound.set_volume(0.2)
        return sound


class OsuCursor:
    def __init__(self):
        self.trail = []
        self.max_trail_len = 20

    def update(self):
        pos = pygame.mouse.get_pos()
        self.trail.append(pos)
        if len(self.trail) > self.max_trail_len:
            self.trail.pop(0)

    def draw(self, screen):
        pos = pygame.mouse.get_pos()
        for i, p in enumerate(self.trail):
            alpha = int((i + 1) / len(self.trail) * 200)
            radius = int((i + 1) / len(self.trail) * 16)
            surf = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(surf, (0, 220, 255), (radius, radius), radius)
            surf.set_alpha(alpha)
            screen.blit(surf, (p[0] - radius, p[1] - radius))

        pygame.draw.circle(screen, (255, 255, 255), pos, 24, width=3)
        pygame.draw.circle(screen, (0, 220, 255), pos, 8)
        pygame.draw.line(screen, (255, 255, 255), (pos[0] - 16, pos[1]), (pos[0] + 16, pos[1]), 2)
        pygame.draw.line(screen, (255, 255, 255), (pos[0], pos[1] - 16), (pos[0], pos[1] + 16), 2)


class BackgroundParticle:
    def __init__(self):
        self.x = random.randint(0, SCREEN_WIDTH)
        self.y = random.randint(0, SCREEN_HEIGHT)
        self.speed = random.uniform(2.0, 4.5)  # Увеличенная скорость фоновых шариков
        self.radius = random.randint(1, 5)
        self.alpha = random.randint(100, 220)

    def update(self):
        self.y -= self.speed
        if self.y < 0:
            self.y = SCREEN_HEIGHT
            self.x = random.randint(0, SCREEN_WIDTH)

    def draw(self, screen):
        surf = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(surf, (100, 240, 255), (self.radius, self.radius), self.radius)
        surf.set_alpha(self.alpha)
        screen.blit(surf, (int(self.x), int(self.y)))


def draw_oscilloscope(screen, song, current_time):
    """Рисует большую и эффектную музыкальную осциллограмму на фоне"""
    if song.y is None:
        return

    sr = song.sr
    sample_idx = int((current_time / 1000.0) * sr)
    window_size = 2048

    if sample_idx + window_size >= len(song.y):
        return

    chunk = song.y[sample_idx: sample_idx + window_size]
    step = max(1, len(chunk) // SCREEN_WIDTH)
    points = []

    center_y = SCREEN_HEIGHT // 2
    amplitude_scale = 250

    for i, val in enumerate(chunk[::step]):
        x = int((i / len(chunk[::step])) * SCREEN_WIDTH)
        y = int(center_y - val * amplitude_scale)
        points.append((x, y))

    if len(points) > 1:
        wave_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.aalines(wave_surf, (0, 150, 255, 30), False, points, 10)
        pygame.draw.aalines(wave_surf, (0, 200, 255, 70), False, points, 5)
        pygame.draw.aalines(wave_surf, (255, 100, 100, 100), False, points, 3)
        pygame.draw.aalines(wave_surf, (255, 255, 255, 180), False, points, 1)
        screen.blit(wave_surf, (0, 0))


class ClickRipple:
    def __init__(self, pos):
        self.pos = pos
        self.radius = 10
        self.alpha = 255

    def update(self):
        self.radius += 8
        self.alpha -= 20

    def draw(self, screen):
        if self.alpha > 0:
            surf_size = int(self.radius * 2 + 10)
            surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
            pygame.draw.circle(surf, (0, 220, 255), (surf_size // 2, surf_size // 2), self.radius, width=3)
            surf.set_alpha(max(0, self.alpha))
            screen.blit(surf, (self.pos[0] - surf_size // 2, self.pos[1] - surf_size // 2))


class Circle:
    def __init__(self, number, pos, hit_time, approach_time, sound):
        self.number = number
        self.color = (0, 220, 255)
        self.size = 130
        self.pos = pos
        self.hit_time = hit_time
        self.approach_time = approach_time
        self.sound = sound
        self.spawn_time = hit_time - approach_time
        self.label = font.render(str(self.number), True, (255, 255, 255))
        self.border_radius = self.size * 3

    def update(self, current_time):
        elapsed = current_time - self.spawn_time
        progress = max(0.0, min(1.0, elapsed / self.approach_time))
        start_radius = self.size * 2.2
        end_radius = self.size / 2
        self.border_radius = start_radius - (start_radius - end_radius) * (progress ** 1.1)

    def draw(self, screen):
        is_red = (self.color == (255, 60, 60))
        glow_size = int(self.size * 2.2 if is_red else self.size * 2.0)
        glow_surf = pygame.Surface((glow_size, glow_size), pygame.SRCALPHA)
        glow_alpha = 100 if is_red else 60
        pygame.draw.circle(glow_surf, self.color, (glow_size // 2, glow_size // 2), int(self.size / 1.3))
        glow_surf.set_alpha(glow_alpha)
        screen.blit(glow_surf, (int(self.pos[0] - glow_size / 2), int(self.pos[1] - glow_size / 2)))

        shadow_size = int(self.size * 1.4)
        shadow_surf = pygame.Surface((shadow_size, shadow_size), pygame.SRCALPHA)
        pygame.draw.circle(shadow_surf, (0, 0, 0), (shadow_size // 2, shadow_size // 2 + 4), int(self.size / 2))
        shadow_surf.set_alpha(150)
        screen.blit(shadow_surf, (int(self.pos[0] - shadow_size / 2), int(self.pos[1] - shadow_size / 2)))

        pygame.draw.circle(screen, self.color, self.pos, int(self.size / 2))
        pygame.draw.circle(screen, (15, 15, 25), self.pos, int(self.size / 2 - 8))
        pygame.draw.circle(screen, self.color, self.pos, int(self.size / 2 - 12))
        pygame.draw.circle(screen, (255, 255, 255), self.pos, max(1, int(self.border_radius)), width=4)

        screen.blit(self.label, (self.pos[0] - self.label.get_width() // 2, self.pos[1] - self.label.get_height() // 2))

    def collidepos(self, pos):
        dist = ((pos[0] - self.pos[0]) ** 2 + (pos[1] - self.pos[1]) ** 2) ** 0.5
        return dist < 75


class Slider:
    def __init__(self, number, start_pos, end_pos, hit_time, duration, approach_time, sound):
        self.number = number
        self.color = (0, 220, 255)
        self.size = 130
        self.start_pos = start_pos
        self.end_pos = end_pos
        self.hit_time = hit_time
        self.duration = duration
        self.end_time = hit_time + duration
        self.approach_time = approach_time
        self.sound = sound
        self.spawn_time = hit_time - approach_time
        self.label = font.render(str(self.number), True, (255, 255, 255))
        self.border_radius = self.size * 3

    def update(self, current_time):
        elapsed = current_time - self.spawn_time
        progress = max(0.0, min(1.0, elapsed / self.approach_time))
        start_radius = self.size * 2.2
        end_radius = self.size / 2
        self.border_radius = start_radius - (start_radius - end_radius) * (progress ** 1.1)

    def get_ball_pos(self, current_time):
        if current_time < self.hit_time:
            return self.start_pos
        elif current_time >= self.end_time:
            return self.end_pos
        else:
            p = (current_time - self.hit_time) / self.duration
            bx = self.start_pos[0] + (self.end_pos[0] - self.start_pos[0]) * p
            by = self.start_pos[1] + (self.end_pos[1] - self.start_pos[1]) * p
            return (int(bx), int(by))

    def draw(self, screen, current_time):
        line_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        pygame.draw.line(line_surf, self.color, self.start_pos, self.end_pos, 30)
        line_surf.set_alpha(80)
        screen.blit(line_surf, (0, 0))

        pygame.draw.line(screen, self.color, self.start_pos, self.end_pos, 18)
        pygame.draw.line(screen, (15, 15, 25), self.start_pos, self.end_pos, 10)

        pygame.draw.circle(screen, self.color, self.end_pos, int(self.size / 2))
        pygame.draw.circle(screen, (15, 15, 25), self.end_pos, int(self.size / 2 - 8))
        pygame.draw.circle(screen, self.color, self.end_pos, int(self.size / 2 - 12))

        ball_pos = self.get_ball_pos(current_time)
        pygame.draw.circle(screen, self.color, ball_pos, int(self.size / 2))
        pygame.draw.circle(screen, (15, 15, 25), ball_pos, int(self.size / 2 - 8))
        pygame.draw.circle(screen, self.color, ball_pos, int(self.size / 2 - 12))

        if current_time < self.hit_time:
            pygame.draw.circle(screen, (255, 255, 255), self.start_pos, max(1, int(self.border_radius)), width=4)
            screen.blit(self.label, (self.start_pos[0] - self.label.get_width() // 2,
                                     self.start_pos[1] - self.label.get_height() // 2))
        else:
            pygame.draw.circle(screen, (255, 255, 255), ball_pos, int(self.size / 2), width=4)

    def collidepos(self, pos):
        dist = ((pos[0] - self.start_pos[0]) ** 2 + (pos[1] - self.start_pos[1]) ** 2) ** 0.5
        return dist < 75


class Particle:
    def __init__(self, pos, color):
        self.x, self.y = pos
        self.color = color
        angle = random.uniform(0, 6.28)
        speed = random.uniform(8, 22)
        self.vx = speed * math.cos(angle)
        self.vy = speed * math.sin(angle)
        self.life = 255
        self.decay = random.randint(14, 25)
        self.radius = random.randint(3, 9)

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.life -= self.decay

    def draw(self, screen):
        if self.life > 0:
            surf_size = int(self.radius * 2)
            surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
            pygame.draw.circle(surf, self.color, (int(self.radius), int(self.radius)), int(self.radius))
            surf.set_alpha(max(0, int(self.life)))
            screen.blit(surf, (int(self.x - self.radius), int(self.y - self.radius)))


class HitEffect:
    def __init__(self, pos, color):
        self.pos = pos
        self.color = color
        self.rings = [
            {'radius': 15.0, 'alpha': 255.0, 'speed_r': 14.0, 'speed_a': -25.0},
            {'radius': 45.0, 'alpha': 220.0, 'speed_r': 10.0, 'speed_a': -18.0},
            {'radius': 80.0, 'alpha': 160.0, 'speed_r': 7.0, 'speed_a': -13.0}
        ]
        self.max_radius = 260.0

    def update(self):
        for ring in self.rings:
            ring['radius'] += ring['speed_r']
            ring['alpha'] += ring['speed_a']
        self.rings = [r for r in self.rings if r['alpha'] > 0]

    def draw(self, screen):
        if not self.rings:
            return
        surf_size = int(self.max_radius * 2 + 40)
        surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
        center = (surf_size // 2, surf_size // 2)

        for ring in self.rings:
            width = max(1, int(10 * (1 - min(1, ring['radius'] / self.max_radius))))
            alpha_val = max(0, int(ring['alpha']))

            ring_surf = pygame.Surface((surf_size, surf_size), pygame.SRCALPHA)
            pygame.draw.circle(ring_surf, self.color, center, int(ring['radius']), width=width)
            ring_surf.set_alpha(alpha_val)
            surf.blit(ring_surf, (0, 0))

        screen.blit(surf, (int(self.pos[0] - center[0]), int(self.pos[1] - center[1])))


def spawn_hit_feedback(pos, color, sound):
    hit_effects.append(HitEffect(pos, color))
    for _ in range(40):
        particles.append(Particle(pos, color))
    if sound:
        sound.play()


class CircleSpawner:
    def __init__(self):
        self.next_number = 1
        self.beatmap_index = 0
        self.beatmap = []
        self.approach_time = 850

    def set_beatmap(self, beatmap, approach_time):
        self.beatmap = beatmap
        self.beatmap_index = 0
        self.next_number = 1
        self.approach_time = approach_time

    def update(self, current_time):
        while self.beatmap_index < len(self.beatmap):
            item_data = self.beatmap[self.beatmap_index]
            item_type = item_data[0]

            if item_type == 'slider':
                _, data, sound = item_data
                first_hit_time = data[0]
            else:
                _, first_hit_time, sound = item_data

            spawn_time = first_hit_time - self.approach_time
            if current_time >= spawn_time:
                self.spawn_object(item_data)
                self.beatmap_index += 1
            else:
                break

    def spawn_object(self, item_data):
        item_type = item_data[0]
        margin = 150
        max_attempts = 25
        start_pos = (0, 0)

        for _ in range(max_attempts):
            if len(game_objects) > 0:
                last_obj = game_objects[-1]
                last_pos = last_obj.pos if isinstance(last_obj, Circle) else last_obj.end_pos

                angle = random.uniform(0, 6.28)
                distance = random.randint(130, 220)
                nx = int(last_pos[0] + math.cos(angle) * distance)
                ny = int(last_pos[1] + math.sin(angle) * distance)
            else:
                nx = random.randint(300, SCREEN_WIDTH - 300)
                ny = random.randint(300, SCREEN_HEIGHT - 300)

            nx = max(margin, min(SCREEN_WIDTH - margin, nx))
            ny = max(margin, min(SCREEN_HEIGHT - margin, ny))
            candidate_pos = (nx, ny)

            overlap = False
            for obj in game_objects:
                obj_pos = obj.pos if isinstance(obj, Circle) else obj.start_pos
                if math.hypot(candidate_pos[0] - obj_pos[0], candidate_pos[1] - obj_pos[1]) < 135:
                    overlap = True
                    break

            if not overlap or len(game_objects) == 0:
                start_pos = candidate_pos
                break
        else:
            start_pos = (nx, ny)

        current_num = self.next_number
        self.next_number += 1

        if item_type == 'slider':
            _, (start_t, duration), sound = item_data
            angle2 = random.uniform(0, 6.28)
            slider_len = random.randint(120, 200)
            ex = int(start_pos[0] + math.cos(angle2) * slider_len)
            ey = int(start_pos[1] + math.sin(angle2) * slider_len)
            ex = max(margin, min(SCREEN_WIDTH - margin, ex))
            ey = max(margin, min(SCREEN_HEIGHT - margin, ey))
            end_pos = (ex, ey)

            game_objects.append(Slider(current_num, start_pos, end_pos, start_t, duration, self.approach_time, sound))
        else:
            _, hit_time, sound = item_data
            game_objects.append(Circle(current_num, start_pos, hit_time, self.approach_time, sound))

        update_object_colors()


class Result:
    def __init__(self, text, color, pos):
        self.label = font_large.render(text, True, color)
        self.pos = pos
        self.alpha = 255.0
        self.y_offset = 0.0

    def update(self):
        self.alpha -= 6.5
        self.y_offset -= 1.8

    def draw(self, screen):
        if self.alpha <= 0:
            if self in results:
                results.remove(self)
            return

        text_surf = self.label.copy()
        text_surf.set_alpha(max(0, int(self.alpha)))
        screen.blit(text_surf, (int(self.pos[0] - text_surf.get_width() / 2),
                                int(self.pos[1] + self.y_offset - text_surf.get_height() / 2)))


class HUD:
    def __init__(self):
        self.hp = 100.0

    def reset(self):
        self.hp = 100.0

    def modify_hp(self, amount):
        self.hp = max(0.0, min(100.0, self.hp + amount))

    def draw(self, screen):
        bar_width = 450
        bar_height = 30
        hp_ratio = self.hp / 100.0
        fill_hp_width = int(bar_width * hp_ratio)
        hp_color = (50, 225, 80) if self.hp > 50 else (255, 200, 0) if self.hp > 25 else (240, 40, 60)

        pygame.draw.rect(screen, (30, 30, 45), pygame.Rect(28, 28, bar_width + 4, bar_height + 4), border_radius=10)
        pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(30, 30, bar_width, bar_height), 2, border_radius=8)
        pygame.draw.rect(screen, hp_color, pygame.Rect(30, 30, fill_hp_width, bar_height), border_radius=8)

        hp_text = font.render(f"HP: {int(self.hp)}%", True, (255, 255, 255))
        screen.blit(hp_text, (bar_width + 55, 26))

        score_text = font_large.render(f"SCORE: {score:06d}", True, (255, 255, 255))

        global combo_scale_timer
        combo_scale = 1.0
        if combo_scale_timer > 0:
            combo_scale = 1.25 + 0.15 * math.sin(combo_scale_timer * 0.5)
            combo_scale_timer -= 1

        base_combo_surf = font.render(f"COMBO: {combo}x", True, (0, 220, 255))
        if combo_scale != 1.0:
            new_w = int(base_combo_surf.get_width() * combo_scale)
            new_h = int(base_combo_surf.get_height() * combo_scale)
            combo_text = pygame.transform.smoothscale(base_combo_surf, (max(1, new_w), max(1, new_h)))
        else:
            combo_text = base_combo_surf

        screen.blit(score_text, (SCREEN_WIDTH - score_text.get_width() - 40, 30))
        screen.blit(combo_text, (SCREEN_WIDTH - combo_text.get_width() - 40, 85))


def load_songs_from_folder():
    songs_dir = "songs"
    if not os.path.exists(songs_dir):
        os.makedirs(songs_dir)

    available_songs = []
    for filename in os.listdir(songs_dir):
        if filename.endswith((".mp3", ".wav", ".ogg")):
            filepath = os.path.join(songs_dir, filename)
            available_songs.append(Song(filename, filepath))
    return available_songs


def song_select_screen(songs):
    selected_index = 0
    if not songs:
        while True:
            screen.fill((15, 15, 22))
            text = font_large.render("Папка 'songs' порожня! Додайте .mp3 файли.", True, (255, 100, 100))
            screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, SCREEN_HEIGHT // 2))
            cursor.update()
            cursor.draw(screen)
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit()

    while True:
        screen.fill((15, 15, 22))

        header_rect = pygame.Rect(0, 0, SCREEN_WIDTH, 140)
        pygame.draw.rect(screen, (22, 22, 35), header_rect)
        pygame.draw.line(screen, (70, 70, 110), (0, 140), (SCREEN_WIDTH, 140), 5)

        title_text = font_large.render("OSU! SELECTION", True, (255, 255, 255))
        screen.blit(title_text, (80, 42))

        for i, song in enumerate(songs):
            y_pos = 180 + i * 130
            card_rect = pygame.Rect(100, y_pos, SCREEN_WIDTH - 200, 105)

            if i == selected_index:
                pygame.draw.rect(screen, (40, 100, 170), card_rect, border_radius=18)
                pygame.draw.rect(screen, (0, 200, 255), card_rect, width=4, border_radius=18)
            else:
                pygame.draw.rect(screen, (25, 25, 38), card_rect, border_radius=18)
                pygame.draw.rect(screen, (60, 60, 85), card_rect, width=2, border_radius=18)

            duration_sec = int(song.duration_ms / 1000)
            mins, secs = divmod(duration_sec, 60)

            song_title_surface = font_large.render(song.title, True, (255, 255, 255))
            details_surface = font.render(f"Объектов: {len(song.beatmap)}  |  Длительность: {mins}:{secs:02d}", True,
                                          (180, 190, 210))

            screen.blit(song_title_surface, (140, y_pos + 16))
            screen.blit(details_surface, (140, y_pos + 60))

        cursor.update()
        cursor.draw(screen)
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_DOWN:
                    selected_index = (selected_index + 1) % len(songs)
                elif event.key == pygame.K_UP:
                    selected_index = (selected_index - 1) % len(songs)
                elif event.key == pygame.K_RETURN:
                    return songs[selected_index]
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                for i in range(len(songs)):
                    y_pos = 180 + i * 130
                    if 100 <= mx <= SCREEN_WIDTH - 100 and y_pos <= my <= y_pos + 105:
                        return songs[i]


def play_game(selected_song):
    global game_objects, results, hit_effects, particles, bg_particles, click_ripples, flash_intensity, combo, score, is_holding_slider, combo_scale_timer
    game_objects = []
    results = []
    hit_effects = []
    particles = []
    bg_particles = [BackgroundParticle() for _ in range(160)]  # Больше фоновых шариков (160 штук)
    click_ripples = []
    flash_intensity = 0
    combo = 0
    score = 0
    is_holding_slider = None
    combo_scale_timer = 0

    hud.reset()
    circle_spawner.set_beatmap(selected_song.beatmap, selected_song.approach_time)

    start_ticks = pygame.time.get_ticks()
    is_game_over = False

    if os.path.exists(selected_song.file_path):
        try:
            pygame.mixer.music.load(selected_song.file_path)
            pygame.mixer.music.play()
        except pygame.error:
            print(f"Помилка відтворення: {selected_song.file_path}")

    while True:
        current_time = pygame.time.get_ticks() - start_ticks
        cursor.update()

        mouse_pressed = pygame.mouse.get_pressed()[0]

        if is_holding_slider:
            if not mouse_pressed:
                results.append(Result("Miss", (255, 0, 0), is_holding_slider.end_pos))
                hud.modify_hp(-10)
                combo = 0
                is_holding_slider = None
            else:
                ball_pos = is_holding_slider.get_ball_pos(current_time)
                mx, my = pygame.mouse.get_pos()
                dist = math.hypot(mx - ball_pos[0], my - ball_pos[1])
                if dist > 75:
                    results.append(Result("Break", (255, 100, 100), ball_pos))
                    hud.modify_hp(-8)
                    combo = 0
                    is_holding_slider = None
                elif current_time >= is_holding_slider.end_time:
                    results.append(Result("Great!", (0, 220, 255), is_holding_slider.end_pos))
                    spawn_hit_feedback(is_holding_slider.end_pos, is_holding_slider.color, is_holding_slider.sound)
                    hud.modify_hp(6)
                    combo += 1
                    combo_scale_timer = 15
                    score += 350 * combo
                    if is_holding_slider in game_objects:
                        game_objects.remove(is_holding_slider)
                    is_holding_slider = None

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.mixer.music.stop()
                    return

            if event.type == pygame.MOUSEBUTTONDOWN and not is_game_over:
                click_ripples.append(ClickRipple(event.pos))
                if not is_holding_slider:
                    for obj in game_objects[:]:
                        if obj.collidepos(event.pos):
                            if isinstance(obj, Circle):
                                diff = abs(current_time - obj.hit_time)
                                if diff < 220:
                                    results.append(Result("300", (0, 220, 255), obj.pos))
                                    spawn_hit_feedback(obj.pos, (0, 220, 255), obj.sound)
                                    flash_intensity = 60
                                    hud.modify_hp(5)
                                    combo += 1
                                    combo_scale_timer = 15
                                    score += 300 * combo
                                elif diff < 380:
                                    results.append(Result("100", (144, 238, 144), obj.pos))
                                    spawn_hit_feedback(obj.pos, (144, 238, 144), obj.sound)
                                    flash_intensity = 35
                                    hud.modify_hp(2)
                                    combo += 1
                                    combo_scale_timer = 15
                                    score += 100 * combo
                                else:
                                    results.append(Result("Miss", (255, 100, 100), obj.pos))
                                    spawn_hit_feedback(obj.pos, (255, 100, 100), obj.sound)
                                    hud.modify_hp(-10)
                                    combo = 0
                                    score += 50

                                game_objects.remove(obj)
                                update_object_colors()
                                break

                            elif isinstance(obj, Slider):
                                diff = abs(current_time - obj.hit_time)
                                if diff < 250:
                                    is_holding_slider = obj
                                    flash_intensity = 30
                                    hud.modify_hp(3)
                                    results.append(Result("Hit!", (255, 165, 0), obj.start_pos))
                                    spawn_hit_feedback(obj.start_pos, obj.color, obj.sound)
                                break

        if not is_game_over:
            circle_spawner.update(current_time)

            for bp in bg_particles:
                bp.update()

            for cr in click_ripples[:]:
                cr.update()
                if cr.alpha <= 0:
                    click_ripples.remove(cr)

            for obj in game_objects[:]:
                obj.update(current_time)
                if isinstance(obj, Circle):
                    if current_time > obj.hit_time + 220:
                        results.append(Result("Miss", (255, 0, 0), obj.pos))
                        hud.modify_hp(-12)
                        combo = 0
                        game_objects.remove(obj)
                        update_object_colors()
                elif isinstance(obj, Slider):
                    if current_time > obj.end_time + 100 and obj != is_holding_slider:
                        if obj in game_objects:
                            game_objects.remove(obj)
                            update_object_colors()

            for effect in hit_effects[:]:
                effect.update()
                if not effect.rings and effect in hit_effects:
                    hit_effects.remove(effect)

            for p in particles[:]:
                p.update()
                if p.life <= 0:
                    particles.remove(p)

            for res in results[:]:
                res.update()

            if hud.hp <= 0:
                is_game_over = True
                pygame.mixer.music.stop()

        bg_color = (12, 12, 22)
        if flash_intensity > 0:
            bg_color = (15 + int(flash_intensity * 0.4), 15 + int(flash_intensity * 0.4),
                        28 + int(flash_intensity * 0.6))
        screen.fill(bg_color)

        for bp in bg_particles:
            bp.draw(screen)

        draw_oscilloscope(screen, selected_song, current_time)

        if flash_intensity > 0:
            flash_surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
            flash_surf.fill((255, 255, 255, flash_intensity))
            screen.blit(flash_surf, (0, 0))
            flash_intensity = max(0, flash_intensity - 10)

        for cr in click_ripples:
            cr.draw(screen)

        for effect in hit_effects:
            effect.draw(screen)

        for p in particles:
            p.draw(screen)

        if not is_game_over:
            for obj in reversed(game_objects):
                if isinstance(obj, Circle):
                    obj.draw(screen)
                else:
                    obj.draw(screen, current_time)

            for result in results:
                result.draw(screen)

            if circle_spawner.beatmap_index >= len(selected_song.beatmap) and len(game_objects) == 0:
                win_label = font_large.render("ТРЕК ЗАВЕРШЕНО! (Натисніть ESC)", True, (50, 225, 80))
                screen.blit(win_label, (SCREEN_WIDTH // 2 - win_label.get_width() // 2,
                                        SCREEN_HEIGHT // 2 - win_label.get_height() // 2))
        else:
            lose_label = font_large.render("GAME OVER / ВИ ПРОГРАЛИ!", True, (255, 50, 50))
            sub_label = font.render("Натисніть ESC для виходу в меню", True, (255, 255, 255))
            screen.blit(lose_label, (SCREEN_WIDTH // 2 - lose_label.get_width() // 2, SCREEN_HEIGHT // 2 - 50))
            screen.blit(sub_label, (SCREEN_WIDTH // 2 - lose_label.get_width() // 2, SCREEN_HEIGHT // 2 + 40))

        hud.draw(screen)
        cursor.draw(screen)

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    pygame.init()
    pygame.mixer.init()
    pygame.display.set_caption("Osu! Fast & Dense Edition")

    info = pygame.display.Info()
    SCREEN_WIDTH, SCREEN_HEIGHT = info.current_w, info.current_h
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.FULLSCREEN)

    clock = pygame.time.Clock()
    pygame.mouse.set_visible(False)

    font = pygame.font.SysFont('Arial', int(SCREEN_WIDTH * 0.015))
    font_large = pygame.font.SysFont('Arial', int(SCREEN_WIDTH * 0.025))

    cursor = OsuCursor()
    circle_spawner = CircleSpawner()
    hud = HUD()

    songs_list = load_songs_from_folder()

    while True:
        chosen_song = song_select_screen(songs_list)
        play_game(chosen_song)