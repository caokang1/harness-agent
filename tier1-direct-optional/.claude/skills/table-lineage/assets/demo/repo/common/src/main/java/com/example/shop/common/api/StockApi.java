package com.example.shop.common.api;

import com.example.shop.common.dto.StockDTO;
import java.util.List;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

@FeignClient(name = "stock-service", path = "/api/stock")
public interface StockApi {

    @GetMapping("/low")
    List<StockDTO> listLowStock(@RequestParam("threshold") Integer threshold);
}
