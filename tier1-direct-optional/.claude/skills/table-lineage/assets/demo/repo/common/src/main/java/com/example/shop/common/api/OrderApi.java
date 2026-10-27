package com.example.shop.common.api;

import com.example.shop.common.dto.OrderItemDTO;
import java.util.List;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

@FeignClient(name = "order-service", path = "/api/order")
public interface OrderApi {

    @GetMapping("/items")
    List<OrderItemDTO> listItems(@RequestParam("orderId") Long orderId);
}
