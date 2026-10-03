import os
import sys
import pygame
import random
import librosa

circles = []
results = []

APPROACH_TIME = 600  # Час звуження кільця (мс)


class Song:
    def __init__(self, title, file_path):
        self.title = title
        self.file_path = file_path
        self.duration_ms = 0
        self.beatmap = []
        self.analyze_audio()

    def analyze_audio(self):
        """Автоматичний аналіз аудіофайлу та генерація кружків під ритм."""
        print(f"Аналіз ритму для: {self.title}... Зачекайте декілька секунд.")
        try:
            # Завантажуємо трек через librosa
            y, sr = librosa.load(self.file_path, sr=None)
            self.duration_ms = int(librosa.get_duration(y=y, sr=sr) * 1000)

            # Знаходимо темп (BPM) та точні кадри бітів (onset detection)
            tempo, beat_frames = librosa.beat.beat_track(y=y, sr=sr)
            # Переводимо кадри у мілісекунди
            beat_times = librosa.frames_to_time(beat_frames, sr=sr)

            # Формуємо бітмап у мілісекундах (відсікаємо першу секунду для підготовки)
            self.beatmap = [int(t * 1000) for t in beat_times if t * 1000 >= 1000]
            print(f"Готово! Згенеровано {len(self.beatmap)} кружків під ритм.")
        except Exception as e:
            print(f"Помилка аналізу файлу ({e}). Використовуємо базовий інтервал.")
            self.duration_ms = 180000
            self.beatmap = [1000 + i * 400 for i in range(400)]


class ColorGenerator:
    def __init__(self):
        self.r, self.g, self.b = (255, 0, 0)
        self.step = 15
        self.rise = True

    def __call__(self):
        if self.rise:
            if self.g < 255:
                self.g += self.step
            elif self.b < 255:
                self.b += self.step
            else:
                self.rise = False
        else:
            if self.b > 0:
                self.b -= self.step
            elif self.g > 0:
                self.g -= self.step
            else:
                self.rise = True
        return (self.r, self.g, self.b)


class Circle:
    def __init__(self, number, pos, hit_time):
        self.color = color_generator()
        self.size = 100
        self.pos = pos
        self.number = number
        self.hit_time = hit_time
        self.spawn_time = hit_time - APPROACH_TIME
        self.label = font.render(str(self.number), True, tuple(255 - v for v in self.color))
        self.label_size = self.label.get_size()
        self.border_radius = self.size * 3

    def update(self, current_time):
        elapsed = current_time - self.spawn_time
        progress = max(0.0, min(1.0, elapsed / APPROACH_TIME))
        start_radius = self.size * 1.5
        end_radius = self.size / 2
        self.border_radius = start_radius - (start_radius - end_radius) * progress

    def draw(self, screen):
        pygame.draw.circle(screen, self.color, self.pos, self.size // 2)
        pygame.draw.circle(screen, (255, 255, 255), self.pos, max(1, int(self.border_radius)), width=5)
        screen.blit(self.label, (self.pos[0] - self.label_size[0] // 2, self.pos[1] - self.label_size[1] // 2))

    def collidepos(self, pos):
        return self.pos[0] - 50 < pos[0] < self.pos[0] + 50 and self.pos[1] - 50 < pos[1] < self.pos[1] + 50


class CircleSpawner:
    def __init__(self):
        self.next_number = 1
        self.beatmap_index = 0
        self.beatmap = []

    def set_beatmap(self, beatmap):
        self.beatmap = beatmap
        self.beatmap_index = 0
        self.next_number = 1

    def update(self, current_time):
        while self.beatmap_index < len(self.beatmap):
            hit_time = self.beatmap[self.beatmap_index]
            spawn_time = hit_time - APPROACH_TIME
            if current_time >= spawn_time:
                self.spawn_circle(hit_time)
                self.beatmap_index += 1
            else:
                break

    def spawn_circle(self, hit_time):
        if len(circles) > 0:
            last_pos = circles[-1].pos
            pos = (random.randint(max(last_pos[0] - 250, 60), min(last_pos[0] + 250, 1280 - 60)),
                   random.randint(max(last_pos[1] - 250, 60), min(last_pos[1] + 250, 720 - 60)))
        else:
            pos = (random.randint(60, 1280 - 60), random.randint(60, 720 - 60))

        attempts = 0
        while any(c.collidepos(pos) for c in circles) and attempts < 10:
            pos = (random.randint(60, 1280 - 60), random.randint(60, 720 - 60))
            attempts += 1

        circles.append(Circle(self.next_number, pos, hit_time))
        self.next_number += 1


class Result:
    def __init__(self, text, color, pos):
        self.label = font.render(text, True, color)
        self.label_size = self.label.get_size()
        self.pos = pos
        self.alpha = 255

    def draw(self, screen):
        if self.alpha <= 0:
            if self in results:
                results.remove(self)
            return
        self.label.set_alpha(self.alpha)
        screen.blit(self.label, (self.pos[0] - self.label_size[0] // 2, self.pos[1] - self.label_size[1] // 2))
        self.alpha -= 5


class HUD:
    def __init__(self):
        self.hp = 100.0
        self.hits = 0
        self.total_targets = 1

    def reset(self, total_targets):
        self.hp = 100.0
        self.hits = 0
        self.total_targets = max(1, total_targets)

    def modify_hp(self, amount):
        self.hp = max(0.0, min(100.0, self.hp + amount))

    def add_hit(self):
        self.hits += 1

    def draw(self, screen):
        # 1. HP Bar
        bar_width = 250
        bar_height = 20
        hp_ratio = self.hp / 100.0
        fill_hp_width = int(bar_width * hp_ratio)

        hp_color = (50, 205, 50) if self.hp > 50 else (255, 215, 0) if self.hp > 25 else (220, 20, 60)

        pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(10, 10, bar_width, bar_height), 2)
        pygame.draw.rect(screen, hp_color, pygame.Rect(10, 10, fill_hp_width, bar_height))

        hp_text = font.render(f"HP: {int(self.hp)}%", True, (255, 255, 255))
        screen.blit(hp_text, (bar_width + 15, 8))

        # 2. Progress Bar
        progress_ratio = min(1.0, self.hits / self.total_targets)
        prog_width = 200
        prog_fill = int(prog_width * progress_ratio)

        pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(1020, 10, prog_width, bar_height), 2)
        pygame.draw.rect(screen, (70, 130, 180), pygame.Rect(1020, 10, prog_fill, bar_height))

        prog_text = font.render(f"{int(progress_ratio * 100)}%", True, (255, 255, 255))
        screen.blit(prog_text, (960, 8))


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
            screen.fill((20, 20, 30))
            text = font_large.render("Папка 'songs' порожня! Додайте .mp3 файли.", True, (255, 100, 100))
            screen.blit(text, (1280 // 2 - text.get_size()[0] // 2, 720 // 2))
            pygame.display.flip()
            for event in pygame.event.get():
                if event.type == pygame.QUIT or (event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE):
                    pygame.quit()
                    sys.exit()

    while True:
        screen.fill((20, 20, 30))
        title_text = font_large.render("Оберіть трек (Клік або Стрілки + Enter):", True, (255, 255, 255))
        screen.blit(title_text, (50, 50))

        for i, song in enumerate(songs):
            y_pos = 130 + i * 60
            rect = pygame.Rect(50, y_pos, 1180, 50)

            if i == selected_index:
                pygame.draw.rect(screen, (60, 120, 200), rect, border_radius=8)
            else:
                pygame.draw.rect(screen, (40, 40, 50), rect, border_radius=8)

            duration_sec = int(song.duration_ms / 1000)
            mins, secs = divmod(duration_sec, 60)
            song_info = f"{song.title}  ({mins}:{secs:02d}) — Кружків: {len(song.beatmap)}"

            song_text = font.render(song_info, True, (255, 255, 255))
            screen.blit(song_text, (70, y_pos + 12))

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

            if event.type == pygame.MOUSEBUTTONDOWN:
                mx, my = event.pos
                for i in range(len(songs)):
                    y_pos = 130 + i * 60
                    if 50 <= mx <= 1230 and y_pos <= my <= y_pos + 50:
                        return songs[i]


def play_game(selected_song):
    global circles, results
    circles = []
    results = []

    hud.reset(len(selected_song.beatmap))
    circle_spawner.set_beatmap(selected_song.beatmap)

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

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    pygame.mixer.music.stop()
                    return

            if event.type == pygame.MOUSEBUTTONDOWN and not is_game_over:
                for circle in circles[:]:
                    if circle.collidepos(event.pos) and circle == circles[0]:
                        diff = abs(current_time - circle.hit_time)

                        if diff < 100:
                            results.append(Result("Perfect!", (28, 170, 214), circle.pos))
                            hud.modify_hp(5)
                        elif diff < 200:
                            results.append(Result("Good", (144, 238, 144), circle.pos))
                            hud.modify_hp(2)
                        else:
                            results.append(Result("Bad", (255, 0, 0), circle.pos))
                            hud.modify_hp(-10)

                        hud.add_hit()
                        circles.remove(circle)
                        break

        if not is_game_over:
            circle_spawner.update(current_time)

            for circle in circles[:]:
                circle.update(current_time)
                if current_time > circle.hit_time + 150:
                    results.append(Result("Miss", (255, 0, 0), circle.pos))
                    hud.modify_hp(-12)
                    hud.add_hit()
                    circles.remove(circle)

            if hud.hp <= 0:
                is_game_over = True
                pygame.mixer.music.stop()

        screen.fill((0, 0, 0))
        hud.draw(screen)

        if not is_game_over:
            for circle in reversed(circles):
                circle.draw(screen)
            for result in results:
                result.draw(screen)

            # Перевірка: якщо спавнер вичерпав усі біти і всі кружки зникли (або трек закінчився)
            if circle_spawner.beatmap_index >= len(selected_song.beatmap) and len(circles) == 0:
                win_label = font_large.render("ТРЕК ЗАВЕРШЕНО! (Натисніть ESC)", True, (50, 205, 50))
                screen.blit(win_label,
                            (1280 // 2 - win_label.get_size()[0] // 2, 720 // 2 - win_label.get_size()[1] // 2))
        else:
            lose_label = font_large.render("GAME OVER / ВИ ПРОГРАЛИ!", True, (255, 0, 0))
            sub_label = font.render("Натисніть ESC для виходу в меню", True, (255, 255, 255))
            screen.blit(lose_label, (1280 // 2 - lose_label.get_size()[0] // 2, 720 // 2 - 30))
            screen.blit(sub_label, (1280 // 2 - sub_label.get_size()[0] // 2, 720 // 2 + 20))

        pygame.display.flip()
        clock.tick(60)


if __name__ == "__main__":
    pygame.init()
    pygame.mixer.init()
    pygame.display.set_caption("Osu! Auto-Beat Generator")

    screen = pygame.display.set_mode((1280, 720))
    clock = pygame.time.Clock()

    color_generator = ColorGenerator()
    font = pygame.font.SysFont('Arial', 24)
    font_large = pygame.font.SysFont('Arial', 32)

    circle_spawner = CircleSpawner()
    hud = HUD()

    songs_list = load_songs_from_folder()

    while True:
        chosen_song = song_select_screen(songs_list)
        play_game(chosen_song)