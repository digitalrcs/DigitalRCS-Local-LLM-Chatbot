// SPDX-License-Identifier: MIT
#pragma once
#include <WiFiClient.h>
#include <atomic>

// HTTPClient polls these virtual methods while waiting for headers/body. Only
// the audio worker touches the socket; the UI task only sets the atomic flag.
class CancellableClient : public WiFiClient {
  const std::atomic<bool>& cancel;
  bool cancelled() {
    if(!cancel.load()) return false;
    WiFiClient::stop();
    setTimeout(0); // also break Stream::readStringUntil on a partial header
    return true;
  }
public:
  explicit CancellableClient(const std::atomic<bool>& flag):cancel(flag) {}
  using WiFiClient::connect;
  int connect(const char* host,uint16_t port,int32_t timeout) override {
    if(cancelled()) return 0;
    int result=WiFiClient::connect(host,port,timeout);
    return cancelled()?0:result;
  }
  int connect(IPAddress ip,uint16_t port,int32_t timeout) override {
    if(cancelled()) return 0;
    int result=WiFiClient::connect(ip,port,timeout);
    return cancelled()?0:result;
  }
  int available() override { return cancelled()?0:WiFiClient::available(); }
  uint8_t connected() override { return cancelled()?0:WiFiClient::connected(); }
  int read() override { return cancelled()?-1:WiFiClient::read(); }
  int read(uint8_t* buffer,size_t size) override { return cancelled()?-1:WiFiClient::read(buffer,size); }
  size_t write(uint8_t value) override { return write(&value,1); }
  size_t write(const uint8_t* buffer,size_t size) override {
    size_t sent=0;
    while(sent<size && !cancelled()) {
      size_t remaining=size-sent;
      size_t n=WiFiClient::write(buffer+sent,remaining>1024?1024:remaining);
      if(!n) break;
      sent+=n;
    }
    return sent;
  }
};
