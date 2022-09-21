import base64
import json
from enum import Enum
from typing import Any, Dict, Optional, Union

from localstack.constants import HEADER_LOCALSTACK_EDGE_URL
from localstack.http import Request, Response
from localstack.utils.aws.aws_responses import parse_query_string
from localstack.utils.strings import short_uid, to_str

# type definition for data parameters (i.e., invocation payloads)
InvocationPayload = Union[Dict, str, bytes]


class ApiGatewayVersion(Enum):
    V1 = "v1"
    V2 = "v2"


class ApiInvocationContext:
    """Represents the context for an incoming API Gateway invocation."""

    request: Request

    # invocation context
    context: Dict[str, Any]
    # authentication info for this invocation
    auth_info: Dict[str, Any]

    # target API/resource details extracted from the invocation
    apigw_version: ApiGatewayVersion
    api_id: str
    stage: str
    account_id: str
    region_name: str
    # resource path, including any path parameter placeholders (e.g., "/my/path/{id}")
    resource_path: str
    integration: Dict
    resource: Dict
    # Invocation path with query string, e.g., "/my/path?test". Defaults to "path", can be used
    #  to overwrite the actual API path, in case the path format "../_user_request_/.." is used.
    _path_with_query_string: str

    # response templates to be applied to the invocation result
    response_templates: Dict

    route: Dict
    connection_id: str
    path_params: Dict

    # response object
    response: Response

    stage_variables: Dict

    # websockets route selection
    ws_route: str

    def __init__(
        self,
        request: Request,
        api_id=None,
        stage=None,
        context=None,
        auth_info=None,
    ):
        self.request = request
        self.context = {"requestId": short_uid()} if context is None else context
        self.auth_info = {} if auth_info is None else auth_info
        self.apigw_version = None
        self.api_id = api_id
        self.stage = stage
        self.region_name = None
        self.account_id = None
        self.integration = None
        self.resource = None
        self.resource_path = None
        self.path_with_query_string = None
        self.response_templates = {}
        self.stage_variables = {}
        self.path_params = {}
        self.route = None
        self.ws_route = None

    @property
    def resource_id(self) -> Optional[str]:
        return (self.resource or {}).get("id")

    # @property
    # def invocation_path(self) -> str:
    #     """Return the plain invocation path, without query parameters."""
    #     path = self.path_with_query_string
    #     return path.split("?")[0]
    #
    # @property
    # def path_with_query_string(self) -> str:
    #     """Return invocation path with query string - defaults to the value of 'path', unless customized."""
    #     return self.request.full_path
    #
    # @path_with_query_string.setter
    # def path_with_query_string(self, new_path: str):
    #     """Set a custom invocation path with query string (used to handle "../_user_request_/.." paths)."""
    #     self._path_with_query_string = new_path

    def query_params(self) -> Dict:
        """Extract the query parameters from the target URL or path in this request context."""
        query_string = self.path_with_query_string.partition("?")[2]
        return parse_query_string(query_string)

    @property
    def integration_uri(self) -> Optional[str]:
        integration = self.integration or {}
        return integration.get("uri") or integration.get("integrationUri")

    @property
    def auth_context(self) -> Optional[Dict]:
        if isinstance(self.auth_info, dict):
            context = self.auth_info.setdefault("context", {})
            if principal := self.auth_info.get("principalId"):
                context["principalId"] = principal
            return context

    @property
    def auth_identity(self) -> Optional[Dict]:
        if isinstance(self.auth_info, dict):
            if self.auth_info.get("identity") is None:
                self.auth_info["identity"] = {}
            return self.auth_info["identity"]

    @property
    def authorizer_type(self) -> str:
        if isinstance(self.auth_info, dict):
            return self.auth_info.get("authorizer_type") if self.auth_info else None

    def is_websocket_request(self):
        upgrade_header = str(self.request.headers.get("upgrade") or "")
        return upgrade_header.lower() == "websocket"

    def is_v1(self):
        """Whether this is an API Gateway v1 request"""
        return self.apigw_version == ApiGatewayVersion.V1

    def cookies(self):
        if cookies := self.request.headers.get("cookie") or "":
            return list(cookies.split(";"))
        return []

    @property
    def is_data_base64_encoded(self):
        try:
            json.dumps(self.request.data) if isinstance(self.request.data, (dict, list)) else to_str(self.request.data)
            return False
        except UnicodeDecodeError:
            return True

    def data_as_string(self) -> str:
        try:
            return (
                json.dumps(self.request.data) if isinstance(self.request.data, (dict, list)) else to_str(self.request.data)
            )
        except UnicodeDecodeError:
            # we string encode our base64 as string as well
            return to_str(base64.b64encode(self.request.data))

    def _extract_host_from_header(self):
        host = self.request.headers.get(HEADER_LOCALSTACK_EDGE_URL) or self.request.headers.get("host", "")
        return host.split("://")[-1].split("/")[0].split(":")[0]

    @property
    def domain_name(self):
        return self._extract_host_from_header()

    @property
    def domain_prefix(self):
        host = self._extract_host_from_header()
        return host.split(".")[0]

    @property
    def method(self):
        return self.request.method

    @property
    def headers(self):
        return self.request.headers

    @property
    def data(self):
        return self.request.data

    @property
    def path(self):
        return self.request.path
