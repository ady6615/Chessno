# Example file showing a basic pygame "game loop"
import pygame
from pathlib import Path

# pygame setup
pygame.init()
screen = pygame.display.set_mode((900, 900))
import Assets as Assets
clock = pygame.time.Clock()
running = True

x=80
y=60

def defaultPosition():
    #50 border + 25 for starting position of the image
    screen.blit(Assets.W_Rook, (x,y))  
    screen.blit(Assets.W_Knight, (x+100,y))
    screen.blit(Assets.W_Bishop, (x+200,y))
    screen.blit(Assets.W_King, (x+300,y))
    screen.blit(Assets.W_Queen, (x+400,y))
    screen.blit(Assets.W_Pawn, (x,y+100))
    # screen.blit(board, (50,50))
    # screen.blit(board, (50,50))
    # screen.blit(board, (50,50))
    # screen.blit(board, (50,50))
    # screen.blit(board, (50,50))
    return 

def displayPieces():
    #check the position matrix of pieces

    return

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
    screen.blit(Assets.board, (50,50))
    defaultPosition()
    # RENDER YOUR GAME HERE

    # flip() the display to put your work on screen
    pygame.display.flip()

    clock.tick(60)  # limits FPS to 60

pygame.quit()