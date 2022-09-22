import logging
from typing import Any, Dict

from werkzeug.exceptions import NotFound

from localstack.constants import HEADER_LOCALSTACK_EDGE_URL
from localstack.http import Request, Response, Router
from localstack.http.dispatcher import Handler
from localstack.services.apigateway.context import ApiInvocationContext
from localstack.services.apigateway.helpers import get_api_region
from localstack.services.apigateway.invocations import invoke_rest_api_from_request

LOG = logging.getLogger(__name__)


def to_invocation_context(
    request: Request, url_params: Dict[str, Any] = None
) -> ApiInvocationContext:
    """
    Converts an HTTP Request object into an ApiInvocationContext.

    :param request: the original request
    :param url_params: the parameters extracted from the URL matching rules
    :return: the ApiInvocationContext
    """
    if url_params is None:
        url_params = {}

    # adjust the X-Forwarded-For header
    x_forwarded_for = request.headers.getlist("X-Forwarded-For")
    x_forwarded_for.append(request.remote_addr)
    x_forwarded_for.append(request.host)
    request.headers["X-Forwarded-For"] = ", ".join(x_forwarded_for)

    # set the x-localstack-edge header, it is used to parse the domain
    request.headers[HEADER_LOCALSTACK_EDGE_URL] = request.host_url.strip("/")

    invocation_context = ApiInvocationContext(
        request=request, api_id=url_params.get("api_id"), stage=url_params.get("stage")
    )
    invocation_context._invocation_path = url_params.get("path")
    invocation_context.region_name = get_api_region(url_params.get("api_id"))
    return invocation_context


class ApigatewayRouter:
    """
    Simple implementation around a Router to manage dynamic restapi routes (routes added by a user through the
    apigateway API).
    """

    router: Router[Handler]

    def __init__(self, router: Router[Handler]):
        self.router = router
        self.registered = False

    def register_routes(self) -> None:
        """Registers parameterized routes for API Gateway user invocations."""
        if self.registered:
            LOG.debug("Skipped API gateway route registration (routes already registered).")
            return
        self.registered = True
        LOG.debug("Registering parameterized API gateway routes.")
        self.router.add(
            "/",
            host="<api_id>.execute-api.<regex('.*'):server>",
            endpoint=self.invoke_rest_api,
            defaults={"path": "", "stage": None},
        )
        self.router.add(
            "/<stage>/",
            host="<api_id>.execute-api.<regex('.*'):server>",
            endpoint=self.invoke_rest_api,
            defaults={"path": ""},
        )
        self.router.add(
            "/<stage>/<path:path>",
            host="<api_id>.execute-api.<regex('.*'):server>",
            endpoint=self.invoke_rest_api,
        )

        # add the localstack-specific _user_request_ routes
        self.router.add(
            "/restapis/<api_id>/<stage>/_user_request_",
            endpoint=self.invoke_rest_api,
            defaults={"path": ""},
        )
        self.router.add(
            "/restapis/<api_id>/<stage>/_user_request_/<path:path>",
            endpoint=self.invoke_rest_api,
        )

    def invoke_rest_api(self, request: Request, **url_params: Dict[str, Any]) -> Response:
        if not get_api_region(url_params["api_id"]):
            return Response(status=404)
        invocation_context = to_invocation_context(request, url_params)
        result = invoke_rest_api_from_request(invocation_context)
        if result is not None:
            return result
        raise NotFound()
