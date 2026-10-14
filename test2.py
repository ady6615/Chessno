matrix = [[6,5,4,3,2,4,5,6],
          [1,1,1,1,1,1,1,1],
          [0,0,0,0,0,0,0,0],
          [0,0,0,0,0,0,0,0],
          [0,0,0,0,0,0,0,0],
          [0,0,0,0,0,0,0,0],
          [1,1,1,1,1,1,1,1],
          [6,5,4,3,2,4,5,6]]

print(matrix[0][1])


for i in range(8):
    for j in range(8):
        if(matrix[i][j]==0):
            print("0",end=" ")
        elif(matrix[i][j]==1):
            print("p",end=" ")
        elif(matrix[i][j]==2):
            print("K",end=" ")
        elif(matrix[i][j]==3):
            print("q",end=" ")
        elif(matrix[i][j]==4):
            print("b",end=" ")
        elif(matrix[i][j]==5):
            print("k",end=" ")
        elif(matrix[i][j]==6):
            print("r",end=" ")
    print("")

