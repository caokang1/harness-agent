package com.example.shop.report.service;

import com.example.shop.common.api.OrderApi;
import com.example.shop.common.dto.OrderItemDTO;
import com.example.shop.report.mapper.DailySalesMapper;
import java.util.List;
import javax.annotation.Resource;
import org.springframework.stereotype.Service;

@Service
public class DailySalesService {

    @Resource
    private OrderApi orderApi;
    @Resource
    private DailySalesMapper dailySalesMapper;

    public void refresh(String day, Long orderId) {
        List<OrderItemDTO> items = orderApi.listItems(orderId);
        long amount = items.stream().mapToLong(i -> i.getPrice() * i.getQty()).sum();
        dailySalesMapper.upsert(day, amount);
    }
}
