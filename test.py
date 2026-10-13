# Example file showing a basic pygame "game loop"
import pygame
from pathlib import Path
# pygame setup
pygame.init()
screen = pygame.display.set_mode((900, 900))
clock = pygame.time.Clock()
running = True
image_path_board = Path("sprites") / "Boards" / "DefaultBoard.png"
image_path_B_Bishop = Path("sprites") / "pieces" / "B_Bishop.png"
image_path_B_Knight = Path("sprites") / "pieces" / "B_Knight.png"
image_path_B_King = Path("sprites") / "pieces" / "B_King.png"
image_path_B_Queen = Path("sprites") / "pieces" / "B_Queen.png"
image_path_B_Rook = Path("sprites") / "pieces" / "B_Rook.png"
image_path_B_Pawn = Path("sprites") / "pieces" / "B_Pawn.png"
image_path_W_Bishop = Path("sprites") / "pieces" / "W_Bishop.png"
image_path_W_Knight = Path("sprites") / "pieces" / "W_Knight.png"
image_path_W_King = Path("sprites") / "pieces" / "W_King.png"
image_path_W_Queen = Path("sprites") / "pieces" / "W_Queen.png"
image_path_W_Rook = Path("sprites") / "pieces" / "W_Rook.png"
image_path_W_Pawn = Path("sprites") / "pieces" / "W_Pawn.png"


board = pygame.image.load(str(image_path_board)).convert_alpha()
B_Bishop = pygame.image.load(str(image_path_B_Bishop)).convert_alpha()
B_Knight = pygame.image.load(str(image_path_B_Knight)).convert_alpha()
B_Kingd = pygame.image.load(str(image_path_B_King)).convert_alpha()
B_Queen = pygame.image.load(str(image_path_B_Queen)).convert_alpha()
B_Rook = pygame.image.load(str(image_path_B_Rook)).convert_alpha()
B_Pawn = pygame.image.load(str(image_path_B_Pawn)).convert_alpha()
W_Bishop = pygame.image.load(str(image_path_W_Bishop)).convert_alpha()
W_Knight = pygame.image.load(str(image_path_W_Knight)).convert_alpha()
W_King = pygame.image.load(str(image_path_W_King)).convert_alpha()
W_Queen = pygame.image.load(str(image_path_W_Queen)).convert_alpha()
W_Rook = pygame.image.load(str(image_path_W_Rook)).convert_alpha()
W_Pawn = pygame.image.load(str(image_path_W_Pawn)).convert_alpha()
x=80
y=60
def defaultPosition():
    #50 border + 25 for starting position of the image
    screen.blit(W_Rook, (x,y))  
    screen.blit(W_Knight, (x+100,y))
    screen.blit(W_Bishop, (x+200,y))
    screen.blit(W_King, (x+300,y))
    screen.blit(W_Queen, (x+400,y))
    screen.blit(W_Pawn, (x,y+100))
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
    screen.blit(board, (50,50))
    defaultPosition()
    # RENDER YOUR GAME HERE

    # flip() the display to put your work on screen
    pygame.display.flip()

    clock.tick(60)  # limits FPS to 60

pygame.quit()