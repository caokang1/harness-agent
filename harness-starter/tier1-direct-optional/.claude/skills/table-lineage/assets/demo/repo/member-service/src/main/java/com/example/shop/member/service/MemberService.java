package com.example.shop.member.service;

import com.example.shop.common.dto.MemberDTO;
import com.example.shop.member.entity.Member;
import com.example.shop.member.mapper.MemberLevelMapper;
import com.example.shop.member.mapper.MemberMapper;
import javax.annotation.Resource;
import org.springframework.stereotype.Service;

@Service
public class MemberService {

    @Resource
    private MemberMapper memberMapper;
    @Resource
    private MemberLevelMapper memberLevelMapper;

    public MemberDTO getMember(Long memberId) {
        Member member = memberMapper.selectById(memberId);
        MemberDTO dto = new MemberDTO();
        dto.setId(member.getId());
        dto.setName(member.getName());
        dto.setLevelName(memberLevelMapper.levelName(member.getLevel()));
        return dto;
    }
}
