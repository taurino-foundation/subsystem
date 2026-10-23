use serde::{Deserialize, Serialize};
use serde_json::Value;

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum RpcId {
    Number(i64),
    String(String),
    Null,
}

impl From<i64> for RpcId {
    fn from(value: i64) -> Self {
        Self::Number(value)
    }
}

impl From<i32> for RpcId {
    fn from(value: i32) -> Self {
        Self::Number(value.into())
    }
}

impl From<&str> for RpcId {
    fn from(value: &str) -> Self {
        Self::String(value.into())
    }
}

impl From<String> for RpcId {
    fn from(value: String) -> Self {
        Self::String(value)
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Request {
    pub jsonrpc: String,
    pub method: String,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub params: Option<Value>,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub id: Option<RpcId>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RpcError {
    pub code: i32,
    pub message: String,

    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub data: Option<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(untagged)]
pub enum Response {
    Success {
        jsonrpc: String,
        result: Value,
        id: RpcId,
    },
    Error {
        jsonrpc: String,
        error: RpcError,
        id: RpcId,
    },
}

pub struct RequestBuilder {
    method: String,
    params: Option<Value>,
    id: Option<RpcId>,
}

impl Request {
    pub fn builder(method: impl Into<String>) -> RequestBuilder {
        RequestBuilder {
            method: method.into(),
            params: None,
            id: None,
        }
    }
}

impl RequestBuilder {
    pub fn params(mut self, params: impl Into<Value>) -> Self {
        self.params = Some(params.into());
        self
    }

    pub fn id(mut self, id: impl Into<RpcId>) -> Self {
        self.id = Some(id.into());
        self
    }

    pub fn notification(mut self) -> Self {
        self.id = None;
        self
    }

    pub fn build(self) -> Request {
        Request {
            jsonrpc: "2.0".into(),
            method: self.method,
            params: self.params,
            id: self.id,
        }
    }
}

pub struct ResponseBuilder {
    id: RpcId,
    result: Option<Value>,
    error: Option<RpcError>,
}

impl Response {
    pub fn builder(id: impl Into<RpcId>) -> ResponseBuilder {
        ResponseBuilder {
            id: id.into(),
            result: None,
            error: None,
        }
    }
}

impl ResponseBuilder {
    pub fn result(mut self, result: impl Into<Value>) -> Self {
        self.result = Some(result.into());
        self.error = None;
        self
    }

    pub fn error(mut self, code: i32, message: impl Into<String>) -> Self {
        self.error = Some(RpcError {
            code,
            message: message.into(),
            data: None,
        });
        self.result = None;
        self
    }

    pub fn error_data(mut self, data: impl Into<Value>) -> Self {
        if let Some(error) = self.error.as_mut() {
            error.data = Some(data.into());
        }
        self
    }

    pub fn build(self) -> Result<Response, &'static str> {
        if let Some(error) = self.error {
            return Ok(Response::Error {
                jsonrpc: "2.0".into(),
                error,
                id: self.id,
            });
        }

        if let Some(result) = self.result {
            return Ok(Response::Success {
                jsonrpc: "2.0".into(),
                result,
                id: self.id,
            });
        }

        Err("Response requires either result or error")
    }
}

pub fn encode<T: Serialize>(message: &T) -> Result<Vec<u8>, rmp_serde::encode::Error> {
    rmp_serde::to_vec_named(message)
}

pub fn decode<'a, T: Deserialize<'a>>(bytes: &'a [u8]) -> Result<T, rmp_serde::decode::Error> {
    rmp_serde::from_slice(bytes)
}
