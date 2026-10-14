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
    #50 border + 25 for starting position of the image
    # screen.blit(Assets.W_Rook, (x,y))  
    # screen.blit(Assets.W_Knight, (x+100,y))
    # screen.blit(Assets.W_Bishop, (x+200,y))
    # screen.blit(Assets.W_King, (x+300,y))
    # screen.blit(Assets.W_Queen, (x+400,y))
    # screen.blit(Assets.W_Pawn, (x,y+100))


    for i in range(8):
        for j in range(8):
            if(ChessMatrix.matrix[i][j]=='0'):
                pass
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

# knight = pygame.transform.scale(knight, (80, 80))
while running:
    
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