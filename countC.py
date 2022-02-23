count_C = [0] * 140

with open("dssp-out.txt", "r") as file:
    lines = file.readlines()
    for line in lines:
        for i in range(139):
            if line[i] == 'C':
                count_C[i] += 1

print(count_C)