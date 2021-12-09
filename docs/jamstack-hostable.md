# Make Interpersonal hostable on Jamstack hosts

Interpersonal would be much improved if it were hostable for free on Netlify, Vercel, and other Jamstack hosts.

It's also important to me that it retains its ability to be deployed on a VM, since VM hosting is never going away.

## Problem - use of Flask

Flask is WSGI, which I don't think is drop in possible to use as a Vercel Lambda or Netlify Function.

There is some async drop-in replacement for Flask, maybe that would be good enough?

See also <./wsgi.md>

## Problem - need for database

Interpersonal requires a sqlite database currently, and we'd need to change that for Jamstack deployment.

The simplest thing to do is to replace it with a jamstack database service, like Railway.app or FaunaDB. I don't super trust these to always be a good fit for personal sites, and unlike static Jamstack hosts I am not that confident they'll be around with free tier for a long time.

We could instead use something like a JSON file in S3 for all our database needs. This increases latency which seems basically fine. However, it means making our users get familiar with S3 and IAM, and costs a few cents/month. The amount of money isn't bad, but the difference between $0 and $1 is significant.

Another way to look at this is, currently Interpersonal requires hosting on a VM, which requires paying for and maintaining a VM. If we can make it so that users don't need to maintain a VM, that's a good thing, and S3 would be sufficient. It would be even better if we could make it so user's don't need to pay anything either, and S3 would not be sufficient for that.

Finally, we could (ab)use a private Git repo for this purpose. This is a bit inelegant, as the user will need to create a separate private repo and give the Github app permission to write to both. On the other hand, there is some elegance in using the same storage backend for both the blog and the server state.
