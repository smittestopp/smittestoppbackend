from . import fhi, helsenorge


def endpoints():
    return [
        ("/lookup", fhi.LookupHandler),
        (r"/lookup/([^/]+)", fhi.LookupResultHandler),
        ("/fhi-egress", fhi.FHIEgressHandler),
        ("/fhi-access-log", fhi.FHIAccessLogHandler),
        ("/deletions", fhi.DeletionsHandler),
        ("/birthyear/([^/]+)", fhi.BirthYearHandler),
        ("/egress", helsenorge.EgressHandler),
        ("/access-log", helsenorge.AccessLogHandler),
        ("/revoke-consent", helsenorge.RevokeConsentHandler),
    ]
