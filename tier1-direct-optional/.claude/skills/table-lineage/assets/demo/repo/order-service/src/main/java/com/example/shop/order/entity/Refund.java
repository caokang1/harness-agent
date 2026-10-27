package com.example.shop.order.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("refund")
public class Refund {
    private Long id;
    private Long orderId;
    private Long amount;
    private Integer status;
}
