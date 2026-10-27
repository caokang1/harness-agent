package com.example.shop.report.entity;

import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

@Data
@TableName("alert_rule")
public class AlertRule {
    private Long id;
    private Integer threshold;
    private Boolean enabled;
}
