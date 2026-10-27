package com.example.shop.common.api;

import com.example.shop.common.dto.MemberDTO;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

@FeignClient(name = "member-service", path = "/api/member")
public interface MemberApi {

    @GetMapping("/get")
    MemberDTO getMember(@RequestParam("memberId") Long memberId);
}
