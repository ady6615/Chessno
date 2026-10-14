import pygame
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent
pygame.init()
image_path_board = Path("sprites") / "Boards" / "DefaultBoard.png"
image_path_B_Bishop = Path("sprites") / "pieces" / "B_Bishop.png"
image_path_B_Knight = Path("sprites") / "pieces" / "B_Knight.png"
image_path_B_King = Path("sprites") / "pieces" / "B_King.png"
image_path_B_Queen = Path("sprites") / "pieces" / "B_Queen.png"
image_path_B_Pawn = Path("sprites") / "pieces" / "B_Pawn.png"
image_path_W_Bishop = Path("sprites") / "pieces" / "W_Bishop.png"
image_path_B_Rook = Path("sprites") / "pieces" / "B_Rook.png"
image_path_W_Knight = Path("sprites") / "pieces" / "W_Knight.png"
image_path_W_King = Path("sprites") / "pieces" / "W_King.png"
image_path_W_Queen = Path("sprites") / "pieces" / "W_Queen.png"
image_path_W_Rook = Path("sprites") / "pieces" / "W_Rook.png"
image_path_W_Pawn = Path("sprites") / "pieces" / "W_Pawn.png"
board = pygame.image.load(str(image_path_board)).convert_alpha()
B_Bishop = pygame.image.load(str(image_path_B_Bishop)).convert_alpha()
B_Knight = pygame.image.load(str(image_path_B_Knight)).convert_alpha()
B_King = pygame.image.load(str(image_path_B_King)).convert_alpha()
B_Queen = pygame.image.load(str(image_path_B_Queen)).convert_alpha()
B_Rook = pygame.image.load(str(image_path_B_Rook)).convert_alpha()
B_Pawn = pygame.image.load(str(image_path_B_Pawn)).convert_alpha()
W_Bishop = pygame.image.load(str(image_path_W_Bishop)).convert_alpha()
W_Knight = pygame.image.load(str(image_path_W_Knight)).convert_alpha()
W_King = pygame.image.load(str(image_path_W_King)).convert_alpha()
W_Queen = pygame.image.load(str(image_path_W_Queen)).convert_alpha()
W_Rook = pygame.image.load(str(image_path_W_Rook)).convert_alpha()
W_Pawn = pygame.image.load(str(image_path_W_Pawn)).convert_alpha()