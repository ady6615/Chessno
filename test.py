# Example file showing a basic pygame "game loop"
import pygame
from pathlib import Path
# pygame setup
pygame.init()
screen = pygame.display.set_mode((900, 900))
clock = pygame.time.Clock()
running = True
image_path = Path("sprites") / "Boards" / "DefaultBoard.png"

knight = pygame.image.load(str(image_path)).convert_alpha()

# knight = pygame.transform.scale(knight, (80, 80))
while running:
    # poll for events
    # pygame.QUIT event means the user clicked X to close your window
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # fill the screen with a color to wipe away anything from last frame
    # screen.fill("purple")
      # Background color
    screen.fill((40, 40, 40))

    # Draw the sprite at (x, y)
    screen.blit(knight, (50,50))
    # RENDER YOUR GAME HERE

    # flip() the display to put your work on screen
    pygame.display.flip()

    clock.tick(60)  # limits FPS to 60

pygame.quit()