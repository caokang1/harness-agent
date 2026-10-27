package com.example.shop.member.mapper;

import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface MemberLevelMapper {

    String levelName(Integer level);
}
