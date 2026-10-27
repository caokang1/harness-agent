package com.example.shop.member.controller;

import com.example.shop.common.api.MemberApi;
import com.example.shop.common.dto.MemberDTO;
import com.example.shop.member.service.MemberService;
import javax.annotation.Resource;
import org.springframework.web.bind.annotation.RestController;

@RestController
public class MemberController implements MemberApi {

    @Resource
    private MemberService memberService;

    @Override
    public MemberDTO getMember(Long memberId) {
        return memberService.getMember(memberId);
    }
}
