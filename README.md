## rancher node autoscale by webhook

ENV
```bash
TOKEN = SECRET_TOKEN
RANCHER_NODEPOOL_URL = https://rancher.company.com/v3/nodePools/c-bsptc:np-4bc8r
RANCHER_VERIFY_SSL = 0
RANCHER_TOKEN = token-8gekp:vqxk672fs6788dvqps6jb89n4cgbfbcf7qf64qsb4b7ztpszhbq5lb
RANCHER_CORDONED_TIME = 3600
```

webhook scale up
```
curl -XPOST http://service:8080/up/SECRET_TOKEN
```
webhook scale down
```
curl -XPOST http://service:8080/down/SECRET_TOKEN
```