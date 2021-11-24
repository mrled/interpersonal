# WSGI, not ASGI

I implemented Interpersonal as a WSGI Flask app, rather than follow Sellout Engine's design of an ASGI Starlette app. In retrospect, this might not have been the best plan, as ASGI is more modern, but I wanted to use WSGI. The benefits of ASGI probably don't apply to my sites, and I already have WSGI infrastructure and experience, so I don't regret this too much. If you want to use Interpersonal for a large, multi-user site, however, you might run into scaling issues.

See also: <https://www.475cumulus.com/single-post/2017/04/03/WSGI-Is-Not-Enough-Anymore>