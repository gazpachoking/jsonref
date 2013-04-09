
from lazyproxy import LazyProxy

a = LazyProxy(lambda: 'aoeu')

print(a)
print('uuu' + a[2])
a += 'oeu'
print(a)
