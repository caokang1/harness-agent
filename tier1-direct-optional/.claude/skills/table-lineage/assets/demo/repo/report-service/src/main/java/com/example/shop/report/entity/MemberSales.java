package com.example.shop.report.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("member_sales")
public class MemberSales {
    private Long id;
    private String month;
    private Long memberId;
    private String memberName;
    private Long amount;
}
