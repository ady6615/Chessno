# Example file showing a basic pygame "game loop"
import pygame
from pathlib import Path
import ChessMatrix
# pygame setup
pygame.init()
screen = pygame.display.set_mode((900, 900))

import Assets as Assets
clock = pygame.time.Clock()
running = True

# x=80
# y=60

def defaultPosition():
    
    for i in range(8):
        for j in range(8):
            if(ChessMatrix.matrix[i][j]=='0'):
                pass
            # Don't draw the piece at its original square while dragging
            if dragging and selected_pos == (row, col):
                continue
            elif(ChessMatrix.matrix[i][j]=='wr'):
                screen.blit(Assets.W_Rook, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='wk'):
                screen.blit(Assets.W_Knight, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='wb'):
                screen.blit(Assets.W_Bishop, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='wa'):
                screen.blit(Assets.W_King, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='wq'):
                screen.blit(Assets.W_Queen, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='wp'):
                screen.blit(Assets.W_Pawn, (GetPixels(j,i)))
            elif(ChessMatrix.matrix[i][j]=='br'):
                screen.blit(Assets.B_Rook, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='bk'):
                screen.blit(Assets.B_Knight, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='bb'):
                screen.blit(Assets.B_Bishop, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='ba'):
                screen.blit(Assets.B_King, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='bq'):
                screen.blit(Assets.B_Queen, (GetPixels(j,i)))  
            elif(ChessMatrix.matrix[i][j]=='bp'):
                screen.blit(Assets.B_Pawn, (GetPixels(j,i)))  
                      
               
def GetPixels(x,y):
    x=x
    y=y
    x=(x*100)+80
    y=(y*100)+60
    return x,y
    # nirav , joy ,ady , parth , pushkar , more
    


def displayPieces():
    #check the position ChessMatrix. of pieces

    return
BOARD_X=50
BOARD_Y=50
SQUARE_SIZE = 100
selected_piece = None
selected_pos = None
dragging = False

# knight = pygame.transform.scale(knight, (80, 80))
while running:

    mouse_x, mouse_y = pygame.mouse.get_pos()
    
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # fill the screen with a color to wipe away anything from last frame
    # screen.fill("purple")
      # Background color
    screen.fill((40, 40, 40))

    if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:

            col = (event.pos[0] - BOARD_X) // SQUARE_SIZE
            row = (event.pos[1] - BOARD_Y) // SQUARE_SIZE

            if 0 <= row < 8 and 0 <= col < 8:
                piece = ChessMatrix.matrix[row][col]

                if piece != 0:
                    selected_piece = piece
                    selected_pos = (row, col)
                    dragging = True

        # Drop the piece
    if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
        if dragging:
            col = (event.pos[0] - BOARD_X) // SQUARE_SIZE
            row = (event.pos[1] - BOARD_Y) // SQUARE_SIZE
            if 0 <= row < 8 and 0 <= col < 8:
                old_row, old_col = selected_pos
                # Move piece in the matrix
                ChessMatrix.matrix[row][col] = selected_piece
                ChessMatrix.matrix[old_row][old_col] = 0
            selected_piece = None
            selected_pos = None
            dragging = False
            
    
    # Draw the sprite at (x, y)
    screen.blit(Assets.board, (50,50))
    defaultPosition()
    # RENDER YOUR GAME HERE
    if dragging:
            image = selected_piece
            rect = image.get_rect(center=pygame.mouse.get_pos())
            screen.blit(image, rect)  
    # flip() the display to put your work on screen
    pygame.display.flip()

    clock.tick(60)  # limits FPS to 60

pygame.quit()