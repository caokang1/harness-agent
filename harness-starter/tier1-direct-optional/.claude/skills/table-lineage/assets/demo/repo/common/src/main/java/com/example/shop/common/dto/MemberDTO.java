package com.example.shop.common.dto;

import lombok.Data;

@Data
public class MemberDTO {
    private Long id;
    private String name;
    private Integer level;
    private String levelName;
    private Long storeId;
}
