"""
数据类型
"""

# 整数：int
int1 = 10
int2 = -10
int3 = 0
print(type(int1), type(int2), type(int3))

# 浮点数：float
float1 = 3.14
float2 = -10.0
float3 = 0.0
print(type(float1), type(float2), type(float3))

# 字符串: str
str1 = "hello"
str2 = '你好'
str3 = "666"
print(type(str1), type(str2), type(str3))

# 布尔值：bool
bool1 = True # 真，条件成立 ==> 1
bool2 = False # 假，条件不成立 ==> 0
print(bool1, type(bool1))
print(1+bool1) # 布尔值和数值相加，答案为2