package com.example.shop.common.dto;

import lombok.Data;

@Data
public class MemberSalesDTO {
    private String month;
    private Long memberId;
    private String memberName;
    private Long amount;
}
