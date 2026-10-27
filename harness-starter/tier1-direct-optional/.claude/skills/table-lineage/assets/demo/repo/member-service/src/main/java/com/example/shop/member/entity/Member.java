package com.example.shop.member.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("member")
public class Member {
    private Long id;
    private String name;
    private Integer level;
    private Long storeId;
}
