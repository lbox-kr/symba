import json

with open("data/birdselectricity/test_data.json") as file:
    data = json.load(file)

cnt = 0
pos_cnt = 0
length = 0
depth = 0
for d in data:
    cnt += 1
    length += len(d['body_text'].split(". "))
    if len(d['program']) > 0:
        pos_cnt += 1
        depth += len(d['program'])

print(length / cnt)
print(depth / pos_cnt)