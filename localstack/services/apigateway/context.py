import base64
import json
from enum import Enum
from typing import Any, Dict, Optional, Union

from localstack.constants import HEADER_LOCALSTACK_EDGE_URL
from localstack.http import Request, Response
from localstack.utils.strings import short_uid, to_str

# type definition for data parameters (i.e., invocation payloads)
InvocationPayload = Union[Dict, str, bytes]


class ApiGatewayVersion(Enum):
    V1 = "v1"
    V2 = "v2"


class ApiInvocationContext:
    """Represents the context for an incoming API Gateway invocation."""

    # Werkzeug Request object
    request: Request
    # Werkzeug Response object
    response: Response

    # HTTP method (GET, POST, etc.) of the request. For some use cases, this is not the same as the
    # HTTP method on the request object, e.g., "TestInvokeMethod".
    _method: Optional[str] = None

    # Invocation path with query string, e.g., "/my/path?test". Defaults to "path", can be used
    #  to overwrite the actual API path, in case the path format "../_user_request_/.." is used.
    _path_with_query_string: Optional[str] = None

    # Invocation path used to call API Gateway routes. It differs from the resource path,
    # which is the actual route configuration (e.g., "/my/path/{id}") whereas the invocation path
    # is the actual path used to invoke the API (e.g., "/my/path/123").
    _invocation_path: Optional[str] = None

    _data: Optional[InvocationPayload] = None

    # Region name (e.g., "us-east-1") of the API Gateway request
    region_name: Optional[str] = None

    # invocation context
    context: Dict[str, Any]
    # authentication info for this invocation
    auth_info: Dict[str, Any]

    # target API/resource details extracted from the invocation
    apigw_version: ApiGatewayVersion
    api_id: str
    stage: str
    account_id: str = None
    # resource path, including any path parameter placeholders (e.g., "/my/path/{id}")
    resource_path: str = None
    integration: Dict = None
    resource: Dict = None

    # response templates to be applied to the invocation result
    response_templates: Dict = None

    route: Dict = None
    connection_id: str = None
    path_params: Dict = None

    stage_variables: Dict = None

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
        self.api_id = api_id
        self.stage = stage
        self.auth_info = auth_info or {}

    @property
    def resource_id(self) -> Optional[str]:
        return (self.resource or {}).get("id")

    @property
    def invocation_path(self) -> str:
        if self._invocation_path.startswith("/"):
            return self._invocation_path
        return f"/{self._invocation_path}"

    @property
    def path_with_query_string(self) -> str:
        return (
            self._path_with_query_string
            or f"{self.invocation_path}?" f"{to_str(self.request.query_string)}"
        )

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
            json.dumps(self._data) if isinstance(self._data, (dict, list)) else to_str(self._data)
            return False
        except UnicodeDecodeError:
            return True

    def data_as_string(self) -> str:
        try:
            return (
                json.dumps(self._data)
                if isinstance(self._data, (dict, list))
                else to_str(self._data)
            )
        except UnicodeDecodeError:
            # we string encode our base64 as string as well
            return to_str(base64.b64encode(self.request.get_data()))

    def _extract_host_from_header(self):
        host = self.request.headers.get(HEADER_LOCALSTACK_EDGE_URL) or self.request.headers.get(
            "host", ""
        )
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
        return self._method or self.request.method

    @property
    def headers(self):
        return self.request.headers

    @property
    def data(self):
        return self.request.data

    @property
    def path(self):
        return self.request.path

    def query_params(self) -> Dict:
        return self.request.args
