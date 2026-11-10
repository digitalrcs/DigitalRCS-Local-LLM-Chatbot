// SPDX-License-Identifier: MIT
#pragma once
#include <cstring>
#include <cctype>
namespace Franky {
inline bool bridgeAddress(const char* url) {
  if(!url || std::strncmp(url,"http://",7) || std::strlen(url)>150) return false;
  const char* host=url+7;const char* colon=std::strchr(host,':');
  size_t length=colon?size_t(colon-host):std::strlen(host);
  if(!length || host[0]=='.' || host[0]=='-' || host[length-1]=='.' || host[length-1]=='-') return false;
  if((length==9&&!std::strncmp(host,"localhost",9)) || !std::strncmp(host,"127.",4)) return false;
  for(size_t i=0;i<length;i++) {
    unsigned char c=host[i];if(!std::isalnum(c)&&c!='.'&&c!='-')return false;
  }
  if(colon) {
    const char* p=colon+1;unsigned port=0;size_t digits=0;
    while(*p) {if(*p<'0'||*p>'9'||++digits>5)return false;port=port*10+(*p++-'0');}
    if(port==0||port>65535)return false;
  }
  return true;
}
}
