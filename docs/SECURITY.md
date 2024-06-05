# Secure configuration of Exact

## Security principles of exact

### Triple isolation
Depending on your project security requirements, you can make your database almost fully immune to all theoretically possible vulnerabilities which could be in Exact.

- All user-submitted expressions are validated with [Evalidate](https://github.com/yaroslaff/evalidate) prior to execution.
- Exact application (recommeded way) runs inside isolated docker environment and has only public data inside
- It's possible to run Exact docker app on different computer, even on different datacenter. So, even if someone could break all security and jump out of docker container, he will be very far from your database and other sensitive data and servers (not closer than from his home).


### Use tokens
While read operations do not require any authentication, write operations (such as update, deleted and reload) must pass token verification. There could be many tokens. If tokens are specified globally and per-dataset, all of them are valid.

~~~
tokens:
  - mytoken
~~~

If tokens aren't specified neither in dataset nor globally (in other words, no tokens are configured), write operations will fail verification.

### IP whitelist
Additonally to tokens, you can allow write operations only from specific IP addresses. Example:
~~~
ip_header: CLIENT
trusted_ips:
  - 127.0.0.0/24
~~~
Here we allow write operations from local network only. 

If Exact runs behind proxy (which is very often), client IP address is taken from request header specified in `ip_header`. (in this example, from header "CLIENT"), header content must start from IPv4 address, e.g. "1.2.3.4" or "1.2.3.4:5678" is OK.

Whitelists can be configured both globally or per-dataset. Request will pass whitelist verification if IP is found in any of them.

If whitelists aren't set, access is allowed from any address.


### allowed_operations
~~~
datasets:
  dummy:
    url: https://dummyjson.com/products?limit=100
    allowed_operations:
      - update
      - delete
~~~

Allowed operations are configured per-dataset. Can contain values: update, delete, reload. Searhing is always allowed.
If not-allowed operation requested, request will be rejected. If allowed_operiations are not set, it's equeal to "all allowed" (update, delete, reload).
Example above allows `update` and `delete`, but not `reload`.


### evalidate configuration
Exact will reject queries if it violates EvalModel. EvalModel is specified in exact.yml as 'model'.

There are four pre-defined models, two of them (`custom` and `extended` allows further configuration)

`model: default` - (default, as you guess) - based on `base` model, but extended with ability to access attributes and call functions. Allowed functions are: `int`, `round`. Allowed attributes are: `startswith`, `endswith`, `upper`, `lower`.

`model: base` - evalidate `base_eval_model` as-is, without any modifications. (no attributes/function calls allowed)

`model: custom` starts with empty EvalModel (you can use it, make request to exact and examine detail of error message to know, what to allow). For paranoids.

`model: extended` is similar to `custom`, but starts with `base_eval_model` and you can customize it later.

To extend `custom`/`extended` models, use following example:
~~~yaml
model: extended
nodes: 
  - Call
  - Attribute
attributes:
  - startswith
  - endswith
  - upper
  - lower
functions:
  - int
  - round
~~~
