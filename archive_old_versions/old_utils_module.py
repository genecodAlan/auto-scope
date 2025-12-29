
size = input("Enter Dimensions in WxH format eg. 4x3: ")
width, height = int(size[:1]), int(size[2:]) 
    
print(width, ",",height)

layout = []

rows = height
col = width

total = [x for x in range(rows * col)]


for i in range(rows):
    layout.append([])
    lane = total[(i*col):(i*col + col)] 
    if i % 2 == 1:
        lane.reverse()
    for j in lane:
        layout[i].append(j)



print(layout)








