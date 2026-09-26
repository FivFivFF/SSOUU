import sys
import pygame
import random

circles = []
results = []


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
    def __init__(self, number, pos):
        self.parent = None
        self.color = color_generator()
        self.size = 100
        self.pos = pos
        self.number = number
        self.label = font.render(str(self.number), True, tuple(255 - value for value in self.color))
        self.label_size = self.label.get_size()
        self.border_radius = self.size * 3
        self.draw()

    def draw(self):
        self.rect = pygame.draw.circle(screen, self.color, self.pos, self.size // 2)
        self.border = pygame.draw.circle(screen, (255, 255, 255), self.pos, self.border_radius // 2, width=5)
        screen.blit(self.label, (self.pos[0] - self.label_size[0] // 2, self.pos[1] - self.label_size[1] // 2))

    def collidepos(self, pos):
        return self.pos[0] - 50 < pos[0] < self.pos[0] + 50 and self.pos[1] - 50 < pos[1] < self.pos[1] + 50


class CircleSpawner:
    def __init__(self):
        self.next_number = 1

    def __call__(self, count=1):
        for _ in range(count):
            if len(circles) > 0:
                pos = (random.randint(max(circles[-1].pos[0] - int(circles[-1].size * 1.5), 0 + 50),
                                      min(circles[-1].pos[0] + int(circles[-1].size * 1.5), 1280 - 50)),
                       random.randint(max(circles[-1].pos[1] - int(circles[-1].size * 1.5), 0 + 50),
                                      min(circles[-1].pos[1] + int(circles[-1].size * 1.5), 720 - 50)))
            else:
                pos = (random.randint(0 + 50, 1280 - 50), random.randint(0 + 50, 720 - 50))
            rect = pygame.Rect(pos[0] - 50, pos[1] - 50, 100, 100)
            while not all(list(map(lambda x: not x.rect.colliderect(rect), circles))):
                pos = (random.randint(max(circles[-1].pos[0] - int(circles[-1].size * 1.5), 0 + 50),
                                      min(circles[-1].pos[0] + int(circles[-1].size * 1.5), 1280 - 50)),
                       random.randint(max(circles[-1].pos[1] - int(circles[-1].size * 1.5), 0 + 50),
                                      min(circles[-1].pos[1] + int(circles[-1].size * 1.5), 720 - 50)))
                rect = pygame.Rect(pos[0] - 50, pos[1] - 50, 100, 100)
            circles.append(Circle(self.next_number, pos))
            self.next_number += 1


class Result:
    def __init__(self, text, color, pos):
        self.label = font.render(text, True, color)
        self.label_size = self.label.get_size()
        self.pos = pos
        self.alpha = 255

    def draw(self):
        if not self.alpha > 0:
            results.remove(self)
        self.label.set_alpha(self.alpha)
        screen.blit(self.label, (self.pos[0] - self.label_size[0] // 2, self.pos[1] - self.label_size[1] // 2))
        self.alpha -= 5


class MusicPointsBar:
    def __init__(self):
        self.value = 100

    def draw(self):
        self.border = pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(10, 10, 200, 20), 2)
        self.bar = pygame.draw.rect(screen, (255, 255, 255), pygame.Rect(10, 10, self.value * 2, 20))


def main():
    music_points_bar.value = 100
    circle_spawn = pygame.USEREVENT + 1
    pygame.time.set_timer(circle_spawn, 750)
    circle_spawner(3)
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                return 1
            if event.type == pygame.MOUSEBUTTONDOWN:
                for circle in circles:
                    if circle.collidepos(event.pos):
                        if circle.number == circles[0].number:
                            if circle.border_radius - circle.size < 20:
                                results.append(Result("+5mp", (28, 170, 214), circle.pos))
                                circles.remove(circle)
                                music_points_bar.value = min(100, music_points_bar.value + 5)
                            elif circle.border_radius - circle.size < 40:
                                results.append(Result("0mp", (144, 238, 144), circle.pos))
                                circles.remove(circle)
                            else:
                                results.append(Result("-10mp", (255, 0, 0), circle.pos))
                                circles.remove(circle)
                                music_points_bar.value -= 10
            if event.type == circle_spawn:
                circle_spawner()

        if len(circles) < 3:
            circle_spawner()

        screen.fill((0, 0, 0))
        music_points_bar.draw()
        if music_points_bar.value > 0:
            for circle in circles[::-1]:
                circle.draw()
            for result in results:
                result.draw()
            if circles[0].border_radius > circles[0].size:
                circles[0].border_radius -= 1
                if circles[0].border_radius < circles[0].size * 2:
                    circles[1].border_radius -= 1
            else:
                results.append(Result("-20mp", (255, 0, 0), circles[0].pos))
                circles.remove(circles[0])
                music_points_bar.value -= 20
            clock.tick(180)
        else:
            lose_label = font.render("Вы проиграли...", True, (255, 255, 255))
            screen.blit(lose_label,
                        (1280 // 2 - lose_label.get_size()[0] // 2, 720 // 2 - lose_label.get_size()[1] // 2))
        pygame.display.flip()


if __name__ == "__main__":
    pygame.init()
    pygame.display.set_caption("Osu! On Python")

    size = 1280, 720
    screen = pygame.display.set_mode(size)

    clock = pygame.time.Clock()

    color_generator = ColorGenerator()
    font = pygame.font.SysFont('Arial', 24)

    circle_spawner = CircleSpawner()

    music_points_bar = MusicPointsBar()

    sys.exit(main())